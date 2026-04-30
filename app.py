import json
import logging
import os
import threading
from datetime import datetime, timedelta
from flask import Flask
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from config import SECRET_KEY, CORS_ORIGIN
from database.db import engine, get_session
from database.models import init_db, Organisation, User, Profile, Changelog
from werkzeug.security import generate_password_hash
from flask import jsonify
from services.rate_limiter import limiter, init_limiter

# ── Flask App ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
# ── Reverse-Proxy-Kompatibilität (Pflicht-Hinweis #5) ─────────────────────────
# Hetzner VPS: Nginx terminiert SSL vor Gunicorn → Flask sieht HTTP ohne ProxyFix.
# ProxyFix muss VOR SESSION_COOKIE_SECURE=True stehen — sonst werden Secure-Cookies
# hinter Nginx dropped weil Flask den Request als HTTP (nicht HTTPS) sieht.
# x_host=1 BEWUSST WEGGELASSEN: getnerve.app ist eine Fixed-Domain hinter Nginx.
# x_host würde X-Forwarded-Host vertrauen — Host-Header-Injection-Vektor falls
# Nginx den Header nicht strikt setzt. Nur x_for + x_proto sind nötig.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config['SECRET_KEY']           = SECRET_KEY
app.config['SESSION_PERMANENT']    = True
app.config['CSS_VERSION']          = '20260421-1'
app.config['MAX_CONTENT_LENGTH']   = 5 * 1024 * 1024  # 5 MB feedback uploads
# ── Session-Cookie-Hardening (LB-10) ──────────────────────────────────────────
# SESSION_COOKIE_SECURE=True nur in Prod (HTTPS). FLASK_DEBUG=true → False (Dev/localhost).
# HINWEIS: app.debug ist unter gunicorn immer False → env-var statt app.debug prüfen.
# ProxyFix muss VOR diesem Block aktiv sein — ohne ProxyFix sieht Flask hinter Nginx
# alle Requests als HTTP, not HTTPS → Secure-Cookies werden dropped.
_debug = os.environ.get('FLASK_DEBUG', '').strip() not in ('', '0', 'false', 'False')
app.config['SESSION_COOKIE_SECURE']         = not _debug  # False lokal, True Prod
app.config['SESSION_COOKIE_HTTPONLY']       = True
app.config['SESSION_COOKIE_SAMESITE']       = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME']    = timedelta(days=14)

if SECRET_KEY == 'dev-secret-change-me' and not os.environ.get('FLASK_DEBUG'):
    raise RuntimeError('[NERVE] SECRET_KEY is insecure — set SECRET_KEY env var before starting in production')

socketio = SocketIO(app, cors_allowed_origins=CORS_ORIGIN, async_mode='threading')

# ── CSRF-Schutz (LB-9) ────────────────────────────────────────────────────────
# WICHTIG: csrf = CSRFProtect(app) NACH socketio = SocketIO(app, ...) — Flask-SocketIO
# registriert seinen WSGI-Handler VOR Flask-Routing; /socket.io/* Requests erreichen
# Flask's before_request-Hooks nicht → CSRFProtect's Hook greift nicht (endpoint=None check).
# Reihenfolge socketio-vor-csrf garantiert SocketIO-WSGI-Level-Interception. (VARIANTE B)
csrf = CSRFProtect(app)

# ── Brute-Force-Schutz (H-20) ─────────────────────────────────────────────────
# Reihenfolge KRITISCH: (1) ProxyFix(app.wsgi_app) [Wave 2] →
#                       (2) CSRFProtect(app) [Wave 3] →
#                       (3) init_limiter(app) [dieser Block]
# Ohne ProxyFix gibt get_remote_address 127.0.0.1 fuer alle Requests hinter Nginx —
# Rate-Limit wird zum globalen Bucket statt per-IP.
# Future Multi-Worker (Block M): in services/rate_limiter.py storage_uri auf
# "redis://localhost:6379" umstellen.
init_limiter(app)

@app.errorhandler(429)
def _handle_rate_limit(e):
    """H-20: Konsistentes JSON-Format fuer 429-Responses (analog Plan 01 Error-Normalisierung)."""
    return jsonify({'ok': False, 'error': 'rate limit exceeded'}), 429

@app.template_filter('fromjson')
def _fromjson(s):
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


def de_currency_filter(value):
    """Formatiert Zahl im deutschen Format mit Euro-Symbol: 1234.56 -> '1.234,56 €'."""
    if value is None:
        return '—'
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    formatted = f"{n:,.2f}"  # '1,234.56' (US)
    # Swap . and , via sentinel
    return formatted.replace(',', '§').replace('.', ',').replace('§', '.') + ' €'

app.jinja_env.filters['de_currency'] = de_currency_filter

# POLISH-52: Markdown-Rendering für PreCall-Briefing (AI-generierter Text mit
# ##Headlines, **bold**, Bullet-Listen). Template nutzt `{{ text | markdown | safe }}`.
# LB-01 (2026-04-21): bleach-Sanitizer gegen XSS via PreCall-Input
# (User-Felder firmenname/branche/ansprechpartner/optinfo -> Haiku -> Briefing
# koennten <img onerror=...> enthalten). Nur Allowlist-Tags erlaubt.
import markdown as _markdown
import bleach
_ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
                 'h1', 'h2', 'h3', 'h4', 'blockquote', 'a']
_ALLOWED_ATTRS = {'a': ['href', 'title']}
def markdown_filter(value):
    if not value:
        return ''
    rendered = _markdown.markdown(value, extensions=['extra', 'sane_lists'])
    return bleach.clean(rendered, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS,
                        strip=True, protocols=['http', 'https', 'mailto'])
app.jinja_env.filters['markdown'] = markdown_filter

# 06.1-r2: Cache-Bust fuer Static-Files — Template ruft static_mtime('pip-launcher.js')
# auf, bekommt die mtime als Integer zurueck, Browser holt bei Aenderung neu.
def _static_mtime(filename):
    import os
    try:
        return str(int(os.path.getmtime(os.path.join(app.static_folder, filename))))
    except Exception:
        return '0'
app.jinja_env.globals['static_mtime'] = _static_mtime

# ── Initialize DB ─────────────────────────────────────────────────────────────
init_db(engine)

# ── Migrate existing DB (add new columns if missing) ──────────────────────────
def _migrate():
    from sqlalchemy import text
    with engine.connect() as conn:
        # ── users ─────────────────────────────────────────────────────────────
        for col, typedef in [
            ('active_profile_id', 'INTEGER'),
            ('letzte_aktivitaet', 'DATETIME'),
            ('trial_ends_at', 'DATETIME'),
            ('is_trial', 'BOOLEAN DEFAULT 0'),
            ('is_coach', 'BOOLEAN DEFAULT 0'),
            # Block 1: Onboarding
            ('vorname', 'VARCHAR(100)'),
            ('nachname', 'VARCHAR(100)'),
            ('onboarding_done', 'BOOLEAN DEFAULT 0'),
            ('erfahrungslevel', 'VARCHAR(50)'),
            ('schmerzpunkt', 'TEXT'),
            ('persoenlich', 'TEXT'),
            # Block 2: Gamification
            ('streak_count', 'INTEGER DEFAULT 0'),
            ('streak_last_date', 'DATE'),
            ('total_points', 'INTEGER DEFAULT 0'),
            ('level', "VARCHAR(50) DEFAULT 'rookie'"),
            # Block 3: Pricing / Nudges
            ('nudge_dismissed', 'TEXT'),
            ('live_calls_used', 'INTEGER DEFAULT 0'),
            ('trainings_used', 'INTEGER DEFAULT 0'),
            # Block 7: Flat-Rate Usage Tracking
            ('minuten_used', 'INTEGER DEFAULT 0'),
            ('trainings_voice_used', 'INTEGER DEFAULT 0'),
            ('usage_reset_date', 'DATE'),
            # Block 4: Notifications / Settings
            ('notif_training_reminder', 'BOOLEAN DEFAULT 1'),
            ('notif_streak_warning', 'BOOLEAN DEFAULT 1'),
            ('notif_achievements', 'BOOLEAN DEFAULT 1'),
            ('notif_coach', 'BOOLEAN DEFAULT 1'),
            ('notif_nudges', 'BOOLEAN DEFAULT 1'),
            ('dashboard_stil', 'TEXT'),
            # Block 8: Dashboard Layout Preference
            ('dashboard_style', "VARCHAR(20) DEFAULT 'vollstaendig'"),
            # Block 6: Changelog
            ('last_seen_changelog', 'VARCHAR(20)'),
            # Block 9: Language Preference
            ('preferred_language', "VARCHAR(10) DEFAULT 'de'"),
            # Block 10: Theme Preference
            ('preferred_theme', "VARCHAR(10) DEFAULT 'dark'"),
            # Block 11: Training Analytics
            ('weekly_goal', 'INTEGER DEFAULT 5'),
            # Block 12: Sales Performance Calculator
            ('avg_deal_wert', 'INTEGER'),
            # Block 13: OAuth — Phase 04.6.1
            ('oauth_provider', 'VARCHAR(50)'),
            ('oauth_id',       'VARCHAR(200)'),
            ('avatar_url',     'VARCHAR(500)'),
            # Phase 04.7.1: Markt-Trennung (FT-Logging)
            ('market',   "VARCHAR(10) NOT NULL DEFAULT 'dach'"),
            ('language', "VARCHAR(10) NOT NULL DEFAULT 'de'"),
        ]:
            try:
                conn.execute(text(f'ALTER TABLE users ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added users.{col}")
            except Exception:
                pass
        # ── organisations ─────────────────────────────────────────────────────
        for col, typedef in [
            ('trial_starts_at', 'DATETIME'),
            ('coach_id', 'INTEGER'),
            ('dsgvo_modus', 'BOOLEAN DEFAULT 1'),
            # Block 3: Pricing
            ('plan_typ', "VARCHAR(50) DEFAULT 'bundle'"),
            ('training_free_calls', 'INTEGER DEFAULT 5'),
            ('live_free_trainings', 'INTEGER DEFAULT 3'),
            # Block 4: Billing / Cancellation
            ('billing_name', 'VARCHAR(200)'),
            ('billing_street', 'VARCHAR(200)'),
            ('billing_zip', 'VARCHAR(20)'),
            ('billing_city', 'VARCHAR(100)'),
            ('billing_country', "VARCHAR(100) DEFAULT 'Deutschland'"),
            ('billing_vat_id', 'VARCHAR(50)'),
            ('cancelled_at', 'DATETIME'),
            ('cancel_reason', 'TEXT'),
            ('cancel_feedback', 'TEXT'),
            # Block 5: Early Access
            ('is_early_access', 'BOOLEAN DEFAULT 0'),
            ('early_access_discount', 'INTEGER DEFAULT 50'),
            # Block 6: Flat-Rate Pricing
            ('minuten_limit', 'INTEGER DEFAULT 1000'),
            ('training_voice_limit', 'INTEGER DEFAULT 50'),
            ('plan_preis', 'INTEGER DEFAULT 49'),
            # Fair-Use Tracking (org-level)
            ('live_minutes_used',      'INTEGER DEFAULT 0'),
            ('training_sessions_used', 'INTEGER DEFAULT 0'),
            ('fair_use_reset_month',   'VARCHAR(7)'),
            # Block 7: Stripe Integration
            ('stripe_customer_id',      'VARCHAR(100)'),
            ('stripe_subscription_id',  'VARCHAR(100)'),
            ('stripe_price_id',         'VARCHAR(100)'),
            ('subscription_status',     "VARCHAR(50) DEFAULT 'inactive'"),
        ]:
            try:
                conn.execute(text(f'ALTER TABLE organisations ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added organisations.{col}")
            except Exception:
                pass
        # ── billing_events ────────────────────────────────────────────────
        for col, typedef in [
            ('stripe_event_id', 'VARCHAR(200)'),
        ]:
            try:
                conn.execute(text(f'ALTER TABLE billing_events ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added billing_events.{col}")
            except Exception:
                pass
        # Create unique index for dedup (SQLite ALTER TABLE cannot add UNIQUE constraint)
        try:
            conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_billing_events_stripe_event_id ON billing_events(stripe_event_id)'))
            conn.commit()
            print("[DB] Migration: created unique index on billing_events.stripe_event_id")
        except Exception:
            pass
        # ── conversation_logs ────────────────────────────────────────────────
        for col, typedef in [
            ('session_mode', "VARCHAR(20) DEFAULT 'meeting'"),
            # Block 12: Sales Performance Calculator
            ('result', 'VARCHAR(20)'),
            # Phase 04.7.1: Markt-Trennung (FT-Logging)
            ('market',   "VARCHAR(10) NOT NULL DEFAULT 'dach'"),
            ('language', "VARCHAR(10) NOT NULL DEFAULT 'de'"),
        ]:
            try:
                conn.execute(text(f'ALTER TABLE conversation_logs ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added conversation_logs.{col}")
            except Exception:
                pass
        # ── Phase 04.7: Superadmin ────────────────────────────────────────────
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_superadmin BOOLEAN DEFAULT 0"))
            conn.commit()
            print("[DB] Migration: added users.is_superadmin")
        except Exception:
            pass
        # ── Phase 04.7 Plan 05: planning_feedback_link Tabelle ───────────────
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS planning_feedback_link (
                    id INTEGER PRIMARY KEY,
                    feedback_id INTEGER NOT NULL REFERENCES feedback(id),
                    planning_title VARCHAR(200) NOT NULL,
                    planning_status VARCHAR(40) NOT NULL DEFAULT 'backlog',
                    created_at DATETIME NOT NULL
                )
            """))
            conn.commit()
            print("[DB] Migration: created planning_feedback_link table")
        except Exception:
            pass
        # ── Phase 04.7 Plan 04: Feedback Tabelle ─────────────────────────────
        for col, typedef in [
            ('screenshot_path',   'VARCHAR(300)'),
            ('context_url',       'VARCHAR(500)'),
            ('status',            "VARCHAR(30) DEFAULT 'new'"),
            ('kategorie',         'VARCHAR(50)'),
            ('rating',            'INTEGER'),
            ('updated_at',        'DATETIME'),
            ('notification_sent', 'BOOLEAN DEFAULT 0'),
        ]:
            try:
                conn.execute(text(f'ALTER TABLE feedback ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added feedback.{col}")
            except Exception:
                pass
        # ── Phase 04.9: personality_types table ──────────────────────────────
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS personality_types (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    org_id INTEGER REFERENCES organisations(id),
                    is_custom BOOLEAN NOT NULL DEFAULT 0,
                    name VARCHAR(100) NOT NULL,
                    icon VARCHAR(10),
                    kurzbeschreibung VARCHAR(300),
                    attribute TEXT NOT NULL DEFAULT '{}',
                    kommentar TEXT,
                    erstellt_am DATETIME
                )
            """))
            conn.commit()
            print("[DB] Migration: created personality_types table")
        except Exception:
            pass
        # ── Phase 04.10: deduplicate system personality_types + add UNIQUE index ─
        try:
            # Remove duplicates: keep only the lowest id per system type name
            conn.execute(text("""
                DELETE FROM personality_types
                WHERE is_custom = 0 AND id NOT IN (
                    SELECT MIN(id) FROM personality_types
                    WHERE is_custom = 0
                    GROUP BY name
                )
            """))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_personality_system_name
                ON personality_types (name) WHERE is_custom = 0 AND user_id IS NULL
            """))
            conn.commit()
            print("[DB] Migration: added unique index on personality_types")
        except Exception:
            pass
        # ── Phase 04.10: deduplicate training_scenarios + add UNIQUE index ─
        try:
            conn.execute(text("""
                DELETE FROM training_scenarios
                WHERE erstellt_von IS NULL AND id NOT IN (
                    SELECT MIN(id) FROM training_scenarios
                    WHERE erstellt_von IS NULL
                    GROUP BY name
                )
            """))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_scenario_system_name
                ON training_scenarios (name) WHERE erstellt_von IS NULL
            """))
            conn.commit()
            print("[DB] Migration: added unique index on training_scenarios")
        except Exception:
            pass
        # ── Phase 04.9: conversation_logs extensions ──────────────────────────
        for col, typedef in [
            ('personality_type_id', 'INTEGER'),
            ('stimmung_history',    'TEXT'),
        ]:
            try:
                conn.execute(text(f'ALTER TABLE conversation_logs ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added conversation_logs.{col}")
            except Exception:
                pass
        # ── Phase 07.1: kb_verlauf fuer Live-Session-Chart ────────────────────
        for col, typedef in [
            ('kb_verlauf', 'TEXT'),
        ]:
            try:
                conn.execute(text(f'ALTER TABLE conversation_logs ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added conversation_logs.{col}")
            except Exception:
                pass
        # ── Phase 04.13: PreCall Intelligence ────────────────────────────────
        for col, typedef in [
            ('precall_briefing', 'TEXT'),
        ]:
            try:
                conn.execute(text(f'ALTER TABLE conversation_logs ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added conversation_logs.{col}")
            except Exception:
                pass
        # ── Phase 04.9: Seed 6 system personality types ───────────────────────
        import json as _json
        _personality_seed = [
            {
                'name': 'Beschäftigter Chef',
                'icon': '\U0001F4BC',
                'kurzbeschreibung': 'Hat keine Zeit. Komm zum Punkt oder er legt auf.',
                'attribute': _json.dumps({
                    'startstimmung': -2, 'geduld': 1, 'skeptik': 3, 'zeitdruck': 5,
                    'auflege_trigger_hart': ['Generischer Opener', 'Preis in ersten 2 Minuten'],
                    'auflege_trigger_weich': ['Lange Einleitung ohne Nutzen', 'Kein konkretes Angebot'],
                    'beispiel_reaktionen': [
                        'Ich habe gerade keine Zeit, schicken Sie mir eine Email.',
                        'Kommen Sie auf den Punkt, ich habe 2 Minuten.',
                        'Was bringt mir das konkret?'
                    ],
                    'verhaltensregeln': 'Du bist ein vielbeschäftigter Geschäftsführer. Du hast keine Geduld für lange Floskeln. Du legst sofort auf wenn der Berater keinen klaren Nutzen in den ersten 30 Sekunden nennt.',
                    'position_profil': 'Geschäftsführer / CEO'
                }, ensure_ascii=False),
            },
            {
                'name': 'Skeptiker',
                'icon': '\U0001F914',
                'kurzbeschreibung': 'Hinterfragt alles. Braucht harte Fakten, keine Floskeln.',
                'attribute': _json.dumps({
                    'startstimmung': -1, 'geduld': 3, 'skeptik': 5, 'zeitdruck': 2,
                    'auflege_trigger_hart': ['Übertriebene Versprechen', 'Ausweichen bei direkter Frage'],
                    'auflege_trigger_weich': ['Unkonkrete Aussagen', 'Keine Referenzen'],
                    'beispiel_reaktionen': [
                        'Das klingt nach Marketing. Was sind die echten Zahlen?',
                        'Haben Sie Referenzen aus unserer Branche?',
                        'Was passiert wenn das Produkt nicht das hält was Sie versprechen?'
                    ],
                    'verhaltensregeln': 'Du bist extrem skeptisch und hinterfragst jede Aussage. Du willst Beweise, Zahlen und Referenzen. Übertreibungen bringen dich sofort zum Aufhängen.',
                    'position_profil': 'Einkaufsleiter / Head of Procurement'
                }, ensure_ascii=False),
            },
            {
                'name': 'Analytiker',
                'icon': '\U0001F4CA',
                'kurzbeschreibung': 'Will Zahlen, Daten, Fakten. Emotionen prallen ab.',
                'attribute': _json.dumps({
                    'startstimmung': 0, 'geduld': 4, 'skeptik': 4, 'zeitdruck': 2,
                    'auflege_trigger_hart': ['Erfundene technische Antworten', 'Nur Emotion statt Fakten'],
                    'auflege_trigger_weich': ['Vage Aussagen ohne Daten', 'Ignorieren technischer Fragen'],
                    'beispiel_reaktionen': [
                        'Welche konkreten KPIs verbessert Ihr Produkt und um wie viel Prozent?',
                        'Wie ist die Systemarchitektur aufgebaut?',
                        'Ich brauche ein detailliertes technisches Datenblatt.'
                    ],
                    'verhaltensregeln': 'Du bist ein analytischer Typ der alles mit Zahlen und Fakten bewertet. Du hörst geduldig zu aber nur wenn Fakten geliefert werden. Emotionale Argumente ignorierst du völlig.',
                    'position_profil': 'IT-Leiter / CTO / Technischer Projektleiter'
                }, ensure_ascii=False),
            },
            {
                'name': 'Freundlicher Ja-Sager',
                'icon': '\U0001F60A',
                'kurzbeschreibung': 'Nett, aber kauft nie. Die Herausforderung: echtes Commitment.',
                'attribute': _json.dumps({
                    'startstimmung': 1, 'geduld': 5, 'skeptik': 1, 'zeitdruck': 1,
                    'auflege_trigger_hart': [],
                    'auflege_trigger_weich': ['Zu direkter Abschlussversuch ohne Rapport'],
                    'beispiel_reaktionen': [
                        'Das klingt super interessant! Schicken Sie mir mal was zu.',
                        'Ja, das können wir gerne mal anschauen, aber gerade ist nicht der beste Zeitpunkt.',
                        'Ich muss das noch mit meinem Kollegen besprechen.'
                    ],
                    'verhaltensregeln': 'Du bist freundlich und hörst alles gerne an, gibst aber nie ein klares Commitment. Du stimmst allem zu aber ohne konkrete nächste Schritte. Die Herausforderung für den Berater ist es echte Verbindlichkeit herauszuholen.',
                    'position_profil': 'Abteilungsleiter / Middle Manager'
                }, ensure_ascii=False),
            },
            {
                'name': 'Aggressiver',
                'icon': '\U0001F4A2',
                'kurzbeschreibung': 'Laut, direkt, provozierend. Ruhe bewahren ist der Schlüssel.',
                'attribute': _json.dumps({
                    'startstimmung': -3, 'geduld': 2, 'skeptik': 3, 'zeitdruck': 4,
                    'auflege_trigger_hart': ['Berater wird defensiv oder emotional'],
                    'auflege_trigger_weich': ['Unsicherheit im Ton', 'Entschuldigungen'],
                    'beispiel_reaktionen': [
                        'Was ist das für ein Anruf? Ich habe besseres zu tun!',
                        'Das ist doch Quatsch, das haben wir schon probiert!',
                        'Sprechen Sie mit mir nicht so als wäre ich ein Idiot.'
                    ],
                    'verhaltensregeln': 'Du bist laut, direkt und manchmal provozierend. Du testest ob der Berater unter Druck ruhig bleibt. Wenn der Berater sachlich und ruhig bleibt respektierst du das. Wenn er defensiv wird oder sich entschuldigt legst du auf.',
                    'position_profil': 'Unternehmer / Inhaber / Selbstständiger'
                }, ensure_ascii=False),
            },
            {
                'name': 'Entscheider',
                'icon': '\U0001F451',
                'kurzbeschreibung': 'Kein Drama, schnelle Entscheidung. Passt oder passt nicht.',
                'attribute': _json.dumps({
                    'startstimmung': 0, 'geduld': 3, 'skeptik': 2, 'zeitdruck': 3,
                    'auflege_trigger_hart': ['Passt offensichtlich nicht zum Unternehmen'],
                    'auflege_trigger_weich': ['Zu viel Smalltalk', 'Kein klares Preismodell'],
                    'beispiel_reaktionen': [
                        'Was kostet es, was bringt es, wann kann ich starten?',
                        'Ich entscheide schnell. Überzeugen Sie mich in 3 Minuten.',
                        'Wenn das passt, machen wir einen Termin für nächste Woche.'
                    ],
                    'verhaltensregeln': 'Du bist ein erfahrener Entscheider der schnell und rational entscheidet. Du willst keine langen Präsentation sondern eine klare Zusammenfassung: Problem, Lösung, Preis, nächster Schritt. Du bist bereit zu kaufen wenn es passt.',
                    'position_profil': 'Geschäftsführer / Vorstand / Partner'
                }, ensure_ascii=False),
            },
        ]
        for pt in _personality_seed:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO personality_types
                        (user_id, org_id, is_custom, name, icon, kurzbeschreibung, attribute, erstellt_am)
                    VALUES
                        (NULL, NULL, 0, :name, :icon, :kurzbeschreibung, :attribute, datetime('now'))
                """), {'name': pt['name'], 'icon': pt['icon'],
                       'kurzbeschreibung': pt['kurzbeschreibung'],
                       'attribute': pt['attribute']})
                conn.commit()
            except Exception:
                pass
        print("[DB] Migration: seeded system personality types")
        # ── Phase 04.12: learning_events ─────────────────────────────────────────────
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS learning_events (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL REFERENCES users(id),
                    event_type   VARCHAR(50) NOT NULL,
                    source_module VARCHAR(20) NOT NULL,
                    source_id    INTEGER,
                    metadata     TEXT,
                    created_at   DATETIME DEFAULT (datetime('now'))
                )
            """))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_learning_events_user_type
                ON learning_events(user_id, event_type, created_at)
            """))
            conn.commit()
            print("[DB] Migration: created learning_events + index")
        except Exception:
            pass
        for col in ['pending_training_recommendation']:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} TEXT"))
                conn.commit()
                print(f"[DB] Migration: added users.{col}")
            except Exception:
                pass
        # Phase 06: consent_text column on profiles
        # NOTE: uses inner engine.connect() with shadowed 'conn' var — older Phase-06 pattern.
        # Phase 08 restores outer conn by re-opening the context after this block.
        try:
            with engine.connect() as _p06_conn:
                _p06_conn.execute(text("ALTER TABLE profiles ADD COLUMN consent_text TEXT"))
                _p06_conn.commit()
            print("[DB] Migration: added profiles.consent_text")
        except Exception:
            pass  # Column already exists
        # ── Phase 08: Pre-Migration DB-Backup vor destruktiver D-02-Migration ──────
        try:
            import shutil
            import os as _os_bk
            _db_path = 'database/nerve.db'
            _backup_path = 'database/nerve.db.bak_pre_v08_01'
            if _os_bk.path.exists(_db_path) and not _os_bk.path.exists(_backup_path):
                shutil.copy(_db_path, _backup_path)
                print(f"[DB] Phase 08 backup created: {_backup_path}")
        except Exception as e:
            print(f"[DB] Phase 08 backup skipped (non-fatal): {e}")
        # ── Phase 08 D-01: objection_events.success → NULLABLE (Table-Rebuild) ─────
        try:
            rows = conn.execute(text("PRAGMA table_info(objection_events)")).fetchall()
            # r = (cid, name, type, notnull, dflt_value, pk)
            success_is_notnull = any(r[1] == 'success' and r[3] == 1 for r in rows)
            if success_is_notnull:
                conn.execute(text("""
                    CREATE TABLE objection_events_new (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        org_id INTEGER,
                        conversation_log_id INTEGER NOT NULL,
                        einwand_typ VARCHAR(100) NOT NULL,
                        success BOOLEAN,
                        created_at DATETIME NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(id),
                        FOREIGN KEY(org_id) REFERENCES organisations(id),
                        FOREIGN KEY(conversation_log_id) REFERENCES conversation_logs(id)
                    )
                """))
                conn.execute(text("INSERT INTO objection_events_new SELECT * FROM objection_events"))
                conn.execute(text("DROP TABLE objection_events"))
                conn.execute(text("ALTER TABLE objection_events_new RENAME TO objection_events"))
                conn.commit()
                print("[DB] Migration v08_01: objection_events.success -> NULLABLE (table rebuilt)")
        except Exception as e:
            print(f"[DB] Phase 08 objection_events rebuild skipped: {e}")
        # ── Phase 08 D-02: Reset POLISH-38.1 Alt-Daten auf NULL (DESTRUKTIV) ───────
        # Cutoff = 2026-04-22 00:00:00 UTC (POLISH-38.1 Commit 585f567 war 2026-04-21 15:11 +0200).
        # Marker-Row in audit_log zur Nachvollziehbarkeit.
        try:
            result = conn.execute(text("""
                UPDATE objection_events SET success = NULL
                WHERE created_at < '2026-04-22 00:00:00'
            """))
            reset_count = result.rowcount if hasattr(result, 'rowcount') else -1
            conn.commit()
            print(f"[DB] Migration v08_01: Reset {reset_count} POLISH-38.1 success-Werte auf NULL")
            # Marker in audit_log — idempotent (INSERT nur wenn noch nicht vorhanden).
            # Rule 2: ohne Idempotenz waechst audit_log bei jedem App-Neustart — nicht akzeptabel.
            try:
                import json as _json_mig
                existing_marker = conn.execute(text(
                    "SELECT COUNT(*) FROM audit_log WHERE action = 'migration_v08_01_reset_success_polish38_1'"
                )).scalar()
                if existing_marker == 0:
                    conn.execute(text("""
                        INSERT INTO audit_log (user_id, action, target_type, target_id, details, created_at)
                        VALUES (NULL, 'migration_v08_01_reset_success_polish38_1', 'objection_events', NULL, :det, CURRENT_TIMESTAMP)
                    """), {'det': _json_mig.dumps({'reset_count': reset_count, 'cutoff_utc': '2026-04-22 00:00:00'})})
                    conn.commit()
                    print("[DB] Migration v08_01: audit_log marker inserted")
            except Exception as _me:
                print(f"[DB] audit_log marker insert skipped: {_me}")
        except Exception as e:
            print(f"[DB] Phase 08 success reset skipped: {e}")
        # ── Phase 08 D-14: conversation_logs.anrede (PreCall Du/Sie Override) ──────
        for col, typedef in [('anrede', 'VARCHAR(10)')]:
            try:
                conn.execute(text(f'ALTER TABLE conversation_logs ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added conversation_logs.{col}")
            except Exception:
                pass
        # ── Phase 08 D-26: prompt_versions.is_default + backfill is_active → default ──
        try:
            conn.execute(text("ALTER TABLE prompt_versions ADD COLUMN is_default BOOLEAN DEFAULT 0"))
            conn.commit()
            print("[DB] Migration: added prompt_versions.is_default")
        except Exception:
            pass
        try:
            # Backfill: bestehende is_active=1 Rows bekommen is_default=1 (single-variant-semantik bleibt erhalten)
            conn.execute(text("UPDATE prompt_versions SET is_default = 1 WHERE is_active = 1"))
            conn.commit()
            print("[DB] Migration v08: prompt_versions.is_default backfilled from is_active=1")
        except Exception:
            pass
        # ── Phase 08.X: objection_events.antwort_text + einwand_text ────────
        for col, typedef in [('antwort_text', 'TEXT'), ('einwand_text', 'TEXT')]:
            try:
                conn.execute(text(f'ALTER TABLE objection_events ADD COLUMN {col} {typedef}'))
                conn.commit()
                print(f"[DB] Migration: added objection_events.{col}")
            except Exception:
                pass
        # ── Phase 08 Plan 06: ewb_ratings Tabelle ─────────────────────────
        # SQLAlchemy's Base.metadata.create_all() erzeugt die Tabelle ueber das
        # EwbRating-Model. Dieser Block ist Fallback-DDL fuer den Fall dass
        # create_all() beim App-Startup nicht alle neuen Models abdeckt (z.B.
        # bei Deploy-Reihenfolge Import vor Create). Idempotent via IF NOT EXISTS.
        try:
            rows = conn.execute(text("PRAGMA table_info(ewb_ratings)")).fetchall()
            if not rows:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ewb_ratings (
                        id INTEGER PRIMARY KEY,
                        conversation_log_id INTEGER NOT NULL,
                        einwand_typ_key VARCHAR(100) NOT NULL,
                        klingt_wie_mensch BOOLEAN NOT NULL,
                        keine_halluzination BOOLEAN NOT NULL,
                        trifft_einwand BOOLEAN NOT NULL,
                        rater_id INTEGER NOT NULL,
                        rated_at DATETIME NOT NULL,
                        UNIQUE(conversation_log_id, einwand_typ_key),
                        FOREIGN KEY(conversation_log_id) REFERENCES conversation_logs(id),
                        FOREIGN KEY(rater_id) REFERENCES users(id)
                    )
                """))
                conn.commit()
                print("[DB] Phase 08 Plan 06: ewb_ratings table created (fallback DDL)")
        except Exception as e:
            print(f"[DB] Phase 08 ewb_ratings create skipped: {e}")
        # ── Phase 08.5: profile_faqs table ───────────────────────────────────────
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS profile_faqs (
                    id INTEGER PRIMARY KEY,
                    profile_id INTEGER NOT NULL REFERENCES profiles(id),
                    frage_muster TEXT NOT NULL,
                    antwort TEXT NOT NULL,
                    kategorie VARCHAR(100),
                    created_at DATETIME,
                    used_count INTEGER DEFAULT 0 NOT NULL
                )
            """))
            conn.commit()
            print("[DB] Migration: created profile_faqs table")
        except Exception as _e:
            print(f"[DB] Migration: profile_faqs skip ({_e})")

        # ── Phase 08.19.3 D-01 + D-02: profile_faqs.mode ─────────────────────────
        try:
            conn.execute(text("ALTER TABLE profile_faqs ADD COLUMN mode VARCHAR(20) NOT NULL DEFAULT 'ki_generated'"))
            conn.commit()
            print("[DB] Migration: added profile_faqs.mode")
            # D-02: Backfill nur beim Erstlauf (ALTER TABLE erfolgreich = Spalte neu)
            # Bestehende Rows erhalten mode='literal' (Backwards-Compat bis User umschaltet)
            conn.execute(text("UPDATE profile_faqs SET mode='literal' WHERE mode='ki_generated'"))
            conn.commit()
            print("[DB] Migration: backfilled profile_faqs.mode='literal' for existing rows")
        except Exception as _e:
            print(f"[DB] Migration: profile_faqs.mode skip ({_e})")
            # column already exists — Backfill wurde beim Erstlauf bereits ausgefuehrt

        # ── Phase 08.5: ft_qa_events table ───────────────────────────────────────
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ft_qa_events (
                    id INTEGER PRIMARY KEY,
                    ft_session_id INTEGER NOT NULL REFERENCES ft_call_sessions(id),
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    market VARCHAR(10) NOT NULL DEFAULT 'dach',
                    language VARCHAR(10) NOT NULL DEFAULT 'de',
                    timestamp_ms INTEGER NOT NULL,
                    utterance_text TEXT,
                    kategorie VARCHAR(50) NOT NULL,
                    confidence FLOAT,
                    faq_matched BOOLEAN DEFAULT 0,
                    faq_id INTEGER REFERENCES profile_faqs(id),
                    antwort_text TEXT,
                    tabu_gefiltert BOOLEAN DEFAULT 0,
                    prompt_version VARCHAR(50) NOT NULL,
                    model_used VARCHAR(100) NOT NULL,
                    created_at DATETIME
                )
            """))
            conn.commit()
            print("[DB] Migration: created ft_qa_events table")
        except Exception as _e:
            print(f"[DB] Migration: ft_qa_events skip ({_e})")

        # ── Phase 08.5: Seed prompt_versions for new modules ─────────────────────
        _phase085_seeds = [
            ('classifier',
             'Du bist ein Echtzeit-Klassifikator fuer Verkaufsgespraeche. Analysiere die letzte Kunden-Aeusserung und klassifiziere in EINE Kategorie: einwand_unknown | frage | smalltalk_none | einwand_known. Antworte NUR als JSON: {"kategorie": "...", "confidence": 0.00, "einwand_zitat": null}. Bei Unsicherheit zwischen einwand_unknown und frage hat frage Vorrang. Wenn der Sprecher einen fertigen Vertriebs-Satz vorliest: smalltalk_none.'),
            ('qa_response',
             'Du beantwortest unbekannte Einwaende oder offene Fragen eines Kunden im Verkaufsgespraech. Anrede: {anrede}. Nutze den Profil-Kontext: {profile_context}. Antworte in maximal 45 Woertern. Niemals apologetisch. Niemals halluzinieren — wenn Daten fehlen, lieber allgemein formulieren.'),
            ('training_kunde',
             'Placeholder v1 — fallback zu KUNDEN_PROMPT_TEMPLATE in training_service.py via _load_training_prompt_template Miss-Logik.'),
            ('training_scoring',
             'Placeholder v1 — fallback zu inline scoring prompt in training_service.py generate_scoring().'),
            ('training_stimmung',
             'Placeholder v1 — fallback zu PERSONALITY_MOOD_PROMPT_SUFFIX in training_service.py.'),
        ]
        for _module, _prompt in _phase085_seeds:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO prompt_versions
                        (version, module, prompt_text, changelog, is_active, is_default, created_at)
                    VALUES
                        ('v1', :module, :prompt, 'Phase 08.5 initial seed', 1, 1, datetime('now'))
                """), {'module': _module, 'prompt': _prompt})
                conn.commit()
            except Exception as _e:
                print(f"[DB] Migration: prompt_versions seed {_module} skip ({_e})")
        print("[DB] Migration: seeded prompt_versions for phase 08.5 modules (classifier, qa_response, training_kunde, training_scoring, training_stimmung)")

        # ── Phase 08.12: User-Migration für onboarding_done (Block-C-Hotfix) ──
        # Block C hat LB-11 Onboarding-Redirect reaktiviert. Bestehende User mit
        # onboarding_done=NULL/False würden im Onboarding-Wizard hängen bleiben.
        # Idempotente Migration: setzt alle bestehenden User auf onboarding_done=1.
        # Safe bei mehrfachem Lauf (UPDATE ohne Effekt wenn schon 1).
        try:
            from sqlalchemy import text as _text_um
            _result = conn.execute(_text_um(
                "UPDATE users SET onboarding_done = 1 "
                "WHERE onboarding_done IS NULL OR onboarding_done = 0"
            ))
            if _result.rowcount > 0:
                print(f"[DB] Migration 08.12: {_result.rowcount} bestehende User auf onboarding_done=True migriert")
            conn.commit()
        except Exception as _e:
            print(f"[DB] Migration 08.12 onboarding_done: skipped ({_e})")

        # ── Phase 08.9: Demo-Profile Flat-Schema → basis.*-Schema Migration ─────
        # 3 Demo-Profile (IDs 2, 3, 4) wurden mit Top-Level 'produkt'/'einwaende'/'phasen'
        # erstellt (vor H-31/HSR-2 BRANCHE_TEMPLATES-Umstellung). Migration ist idempotent:
        # Profile die bereits 'basis'-Key haben, werden nicht angefasst.
        # Down-Migration nicht noetig: SQLite/Dev-Only-Demo-Daten, kein Produktiv-State.
        try:
            import json as _json2
            from sqlalchemy import text as _text2
            _profile_rows = conn.execute(_text2("SELECT id, daten FROM profiles WHERE id IN (2, 3, 4)")).fetchall()
            for _row in _profile_rows:
                _pid, _daten_str = _row[0], _row[1]
                if not _daten_str:
                    continue
                try:
                    _daten = _json2.loads(_daten_str)
                except Exception:
                    continue
                if not isinstance(_daten, dict):
                    continue
                # Idempotenz-Check: wenn 'basis' bereits vorhanden, ueberspringen
                if 'basis' in _daten:
                    continue
                # Flat-Schema erkannt: 'produkt' oder 'einwaende' auf Top-Level
                # Keiner der beiden Keys vorhanden — kein Flat-Schema (leer oder unbekanntes Format)
                if 'produkt' not in _daten and 'einwaende' not in _daten:
                    print(f"[DB] Migration 08.9: Profil ID {_pid} hat keine Flat-Schema-Keys — uebersprungen")
                    continue
                # Umstrukturieren
                _basis = {
                    'produktbeschreibung': _daten.pop('produkt', ''),
                    'einwaende': _daten.pop('einwaende', []),
                    'phasen': _daten.pop('phasen', []),
                }
                _daten['basis'] = _basis
                conn.execute(
                    _text2("UPDATE profiles SET daten = :daten WHERE id = :pid"),
                    {'daten': _json2.dumps(_daten, ensure_ascii=False), 'pid': _pid}
                )
                conn.commit()
                print(f"[DB] Migration 08.9: Profil ID {_pid} auf basis.*-Schema migriert")
        except Exception as _e:
            print(f"[DB] Migration 08.9 Demo-Profile: {_e}")

        # ── Phase 08.10 H-21: oauth_id UNIQUE-Constraint ─────────────────────────
        # Partielle UNIQUE-Index auf NOT-NULL-Werte (SQLite: WHERE oauth_id IS NOT NULL).
        # Idempotent via IF NOT EXISTS. STOPS-Behavior bei Duplicates: sys.exit(1).
        try:
            import sys as _sys
            # 1. Duplicate-Check VOR Constraint-Anlage
            dup_row = conn.execute(text(
                "SELECT oauth_id FROM users WHERE oauth_id IS NOT NULL "
                "GROUP BY oauth_id HAVING COUNT(*) > 1 LIMIT 1"
            )).fetchone()
            if dup_row:
                # H-21: STOPS — Duplicate oauth_ids gefunden. Manuelle Bereinigung nötig vor Deploy.
                all_dups = conn.execute(text(
                    "SELECT oauth_id, COUNT(*) as cnt FROM users WHERE oauth_id IS NOT NULL "
                    "GROUP BY oauth_id HAVING COUNT(*) > 1"
                )).fetchall()
                print("[DB] FEHLER: Duplicate oauth_ids gefunden — NERVE stoppt:", file=_sys.stderr)
                for _row in all_dups:
                    print(f"  oauth_id={_row[0]}  (count={_row[1]})", file=_sys.stderr)
                print("[DB] Bitte oauth_id-Duplicates manuell bereinigen, dann neu starten.", file=_sys.stderr)
                _sys.exit(1)
            else:
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_oauth_id "
                    "ON users(oauth_id) WHERE oauth_id IS NOT NULL"
                ))
                conn.commit()
                print("[DB] Migration: uq_users_oauth_id UNIQUE-Index OK")
        except SystemExit:
            raise  # sys.exit() nicht abfangen
        except Exception as _e:
            print(f"[DB] oauth_id UNIQUE-Index Migration-Fehler: {_e}")

        # ── Phase 08.10 H-18: email_confirmed Column für Microsoft-OAuth Email-Verification ──
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_confirmed BOOLEAN DEFAULT 1"))
            conn.commit()
            print("[DB] Migration: added users.email_confirmed")
        except Exception:
            pass  # Bereits existiert
        # ── Phase 08.13: ApiCostLog Latenz + Call-Site ────────────────────────
        try:
            conn.execute(text("ALTER TABLE api_cost_log ADD COLUMN latency_ms INTEGER"))
            conn.commit()
            print("[DB] Migration: added api_cost_log.latency_ms")
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE api_cost_log ADD COLUMN call_site VARCHAR(50)"))
            conn.commit()
            print("[DB] Migration: added api_cost_log.call_site")
        except Exception:
            pass

        # ── Phase 08.14: ApiRate Seed fuer sonnet-4-5-20251022 + haiku-4-5-20251001 (cache_read/write) ────
        try:
            from database.models import ApiRate
            _needed = [
                ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_input_tokens',       0.003,   'USD'),
                ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_output_tokens',      0.015,   'USD'),
                ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_cache_read_tokens',  0.0003,  'USD'),
                ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_cache_write_tokens', 0.00375, 'USD'),
                ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_input_tokens',       0.00025, 'USD'),
                ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_output_tokens',      0.00125, 'USD'),
                ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_cache_read_tokens',  0.000025,'USD'),
                ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_cache_write_tokens', 0.0003,  'USD'),
            ]
            with engine.connect() as _conn:
                for _provider, _model, _unit, _price, _currency in _needed:
                    _exists = _conn.execute(
                        text("SELECT 1 FROM api_rates WHERE provider=:p AND model=:m AND unit_type=:u AND active=1"),
                        {'p': _provider, 'm': _model, 'u': _unit}
                    ).fetchone()
                    if not _exists:
                        from datetime import datetime as _dt
                        _now = _dt.utcnow()
                        _conn.execute(
                            text("INSERT INTO api_rates (provider, model, unit_type, price_per_unit, currency, active, source_url, last_checked_at, created_at) VALUES (:p,:m,:u,:price,:cur,1,'seed:2026-04-27',:now,:now)"),
                            {'p': _provider, 'm': _model, 'u': _unit, 'price': _price, 'cur': _currency, 'now': _now}
                        )
                        print(f"[DB] ApiRate seeded: {_model} {_unit}")
                _conn.commit()
        except Exception as _e:
            print(f"[DB] ApiRate seed (08.14) failed (non-fatal): {_e}")

        # ── Phase 08.19.3 D-03/D-04/D-05: daten.fragen -> profile_faqs Migration ──
        _migrate_fragen_to_faqs()

    # ── Phase 08.20: Batch-Migration alle Profile -> LATEST_SCHEMA_VERSION (v4) ──
    # Idempotent: Profile mit schema_version >= LATEST_SCHEMA_VERSION werden uebersprungen.
    # Muss NACH den ALTER TABLE Blocks laufen (kein ALTER TABLE hier — nur daten-JSON).
    # Acceptable at startup for NERVE's current profile count (<=20); revisit if >1000 profiles
    try:
        from database.db import get_session as _get_session
        from database.models import Profile as _Profile
        import json as _json
        from services.profile_schema import _migrate_profile_data as _mpd, LATEST_SCHEMA_VERSION as _LATEST_VER

        _db = _get_session()
        try:
            _profiles = _db.query(_Profile).all()
            _migrated_count = 0
            _skipped_count = 0
            for _p in _profiles:
                try:
                    _daten = _json.loads(_p.daten) if _p.daten else {}
                except Exception:
                    _daten = {}
                _version = _daten.get('schema_version') or 1
                if _version >= _LATEST_VER:
                    _skipped_count += 1
                    continue
                # Profil-ID fuer Audit-Log in _migrate_profile_data() injizieren
                _daten['_migration_profile_id'] = _p.id
                _daten_migrated = _mpd(_daten)
                # _migration_profile_id nicht in DB speichern (Hilfsvariable)
                _daten_migrated.pop('_migration_profile_id', None)
                _p.daten = _json.dumps(_daten_migrated, ensure_ascii=False)
                _migrated_count += 1
            _db.commit()
            if _migrated_count > 0:
                print(f"[Schema] Batch-Migration v3->v4: {_migrated_count} Profile migriert, {_skipped_count} uebersprungen")
            else:
                print(f"[Schema] Batch-Migration v3->v4: alle {_skipped_count} Profile bereits auf v4")
        finally:
            _db.close()
    except Exception as _e:
        print(f"[Schema] Batch-Migration v3->v4 FEHLER (nicht kritisch): {_e}")


def _migrate_fragen_to_faqs():
    """Idempotente Migration: daten.fragen Eintraege -> profile_faqs rows (mode='ki_generated').
    D-03: Exact-Match + TRIM Idempotenz-Check.
    D-04: daten.fragen key auf [] setzen (nicht entfernen).
    D-05: Laeuft gegen alle Profile (Andre's Profil 6 + System-Profil 7 inkl.).
    MUST NOT raise — logs expected errors, raises on unexpected.
    """
    import json as _json
    from sqlalchemy import text
    _is_sqlite = str(engine.url).startswith('sqlite')
    try:
        with engine.connect() as _conn:
            if _is_sqlite:
                try:
                    _conn.execute(text("BEGIN EXCLUSIVE"))
                except Exception as _e:
                    print(f"[DB] _migrate_fragen_to_faqs: BEGIN EXCLUSIVE failed: {_e}")
                    return
            else:
                try:
                    _conn.execute(text("SELECT pg_advisory_xact_lock(81930)"))
                except Exception as _e:
                    print(f"[DB] _migrate_fragen_to_faqs: pg_advisory_xact_lock failed: {_e}")
                    return

            # Load all profiles
            _profiles = _conn.execute(text("SELECT id, daten FROM profiles")).fetchall()
            _migrated = 0
            _skipped = 0
            for _row in _profiles:
                _pid = _row[0]
                try:
                    _daten = _json.loads(_row[1] or '{}')
                except Exception:
                    continue
                _fragen = _daten.get('fragen') or []
                if not _fragen:
                    continue
                _changed = False
                for _f in _fragen:
                    _frage = (_f.get('frage') or '').strip() if isinstance(_f, dict) else str(_f).strip()
                    _antwort = (_f.get('antwort') or '').strip() if isinstance(_f, dict) else ''
                    if not _frage:
                        continue
                    # Idempotenz: Exact Match + TRIM (D-03)
                    try:
                        _exists = _conn.execute(
                            text("SELECT EXISTS(SELECT 1 FROM profile_faqs WHERE profile_id=:pid AND frage_muster=trim(:frage))"),
                            {'pid': _pid, 'frage': _frage}
                        ).scalar()
                    except Exception as _e:
                        # Known: constraint check failure — log context and continue
                        print(f"[DB] _migrate_fragen_to_faqs: idempotency check skip (profile_id={_pid}, frage={_frage!r:.40}): {_e}")
                        _skipped += 1
                        continue
                    if _exists:
                        _skipped += 1
                        continue
                    try:
                        _conn.execute(
                            text("""INSERT INTO profile_faqs (profile_id, frage_muster, antwort, kategorie, created_at, used_count, mode)
                                    VALUES (:pid, :frage, :antwort, 'Sonstiges', datetime('now'), 0, 'ki_generated')"""),
                            {'pid': _pid, 'frage': _frage, 'antwort': _antwort}
                        )
                        _migrated += 1
                        _changed = True
                    except Exception as _e:
                        # Known: duplicate insert on re-run — log context and continue
                        print(f"[DB] _migrate_fragen_to_faqs: insert skip (profile_id={_pid}, frage={_frage!r:.40}): {_e}")
                        _skipped += 1
                        continue
                # D-04: daten.fragen key auf [] setzen (nicht entfernen)
                if _changed or _fragen:
                    _daten['fragen'] = []
                    _conn.execute(
                        text("UPDATE profiles SET daten=:daten WHERE id=:pid"),
                        {'daten': _json.dumps(_daten, ensure_ascii=False), 'pid': _pid}
                    )
            _conn.commit()
            print(f"[DB] _migrate_fragen_to_faqs: migrated={_migrated} skipped={_skipped}")
    except Exception as _e:
        # Unexpected error in outer advisory-lock body — log and raise so startup log is visible
        app.logger.error(f"[DB] _migrate_fragen_to_faqs: FAILED at unexpected error: {_e}")
        raise


_migrate()


def _seed_founder_dashboard_defaults():
    """Phase 04.7.2 — idempotenter Seed von FixedCost + ApiRate + ExchangeRate-Fallback.
    Re-run-safe: prueft COUNT pro Tabelle vor INSERT.
    """
    from database.db import SessionLocal
    from database.models import FixedCost, ApiRate, ExchangeRate
    from datetime import date
    db = SessionLocal()
    try:
        # --- FixedCost Seed (D-10 Briefing-Defaults) ---
        if db.query(FixedCost).count() == 0:
            defaults = [
                ('Hetzner CX22 VPS',         4.00,  19.00, 'monthly', '4806', 52),
                ('nerve.app Domain',         1.25,  19.00, 'monthly', '4806', 57),
                ('Kontist Geschaeftskonto',  4.95,  19.00, 'monthly', '4970', 57),
                ('count.tax Steuerberater',  150.00, 19.00, 'monthly', '4950', 57),
                ('Homeoffice Tagespauschale', 6.00, 0.00,  'per_day', '4590', 65),
            ]
            for name, amt, vat, cycle, skr, line in defaults:
                db.add(FixedCost(name=name, amount_eur=amt, vat_rate=vat,
                                 cycle=cycle, skr03=skr, eur_line=line, active=True))
            print(f"[DB] Seeded {len(defaults)} fixed_costs (Phase 04.7.2)")

        # --- ApiRate Seed (Briefing Default-Preise) ---
        if db.query(ApiRate).count() == 0:
            rates = [
                ('anthropic',  'haiku-4-5',       'per_1k_input_tokens',  0.00025, 'USD'),
                ('anthropic',  'haiku-4-5',       'per_1k_output_tokens', 0.00125, 'USD'),
                ('anthropic',  'sonnet-4',        'per_1k_input_tokens',  0.003,   'USD'),
                ('anthropic',  'sonnet-4',        'per_1k_output_tokens', 0.015,   'USD'),
                ('deepgram',   'nova-2',          'per_minute',           0.0036,  'USD'),
                ('elevenlabs', 'multilingual-v2', 'per_1k_chars',         0.30,    'USD'),
                ('stripe',     'card',            'percent',              0.014,   'EUR'),
                ('stripe',     'card',            'fixed_per_tx',         0.25,    'EUR'),
            ]
            for provider, model, unit_type, price, currency in rates:
                db.add(ApiRate(provider=provider, model=model, unit_type=unit_type,
                               price_per_unit=price, currency=currency, active=True,
                               source_url=f'briefing:2026-03-31/{provider}'))
            print(f"[DB] Seeded {len(rates)} api_rates (Phase 04.7.2)")

        # --- ExchangeRate Fallback-Seed ---
        if db.query(ExchangeRate).count() == 0:
            db.add(ExchangeRate(date=date.today(), currency_pair='USD_EUR',
                                rate=0.92, source='seed'))
            print("[DB] Seeded initial USD_EUR fallback rate=0.92 (Phase 04.7.2)")

        db.commit()
    except Exception as e:
        print(f"[DB] _seed_founder_dashboard_defaults failed: {e}")
        db.rollback()
    finally:
        db.close()


_seed_founder_dashboard_defaults()


# ── Phase 04.7.2 — Wechselkurs-Scheduler (Frankfurter daily 06:00 UTC) ────────
try:
    from services.exchange_rates import start_scheduler
    start_scheduler()
except Exception as _fx_e:
    print(f"[FX] scheduler start skipped: {_fx_e}")


def _seed_prompt_versions(db=None):
    from database.db import SessionLocal
    from database.models import PromptVersion
    from services.claude_service import (
        SYSTEM_PROMPT_BASE,
        COACHING_PROMPT_BASE,
    )
    from routes.app_routes import OBJECTION_TRIGGER_PROMPT_BASE
    from services.training_service import TRAINING_PERSONA_PROMPT_BASE

    # ewb_ranking module removed in Phase 04.8 (D-08): rank_ewb Haiku call
    # deleted in favor of deterministic phase-based button tables.
    # api_frage module removed in Phase 08.11 (Block F): Classic-View-Deprecation.
    modules = [
        ('assistant_live',    SYSTEM_PROMPT_BASE),
        ('coaching_live',     COACHING_PROMPT_BASE),
        ('objection_trigger', OBJECTION_TRIGGER_PROMPT_BASE),
        ('training_persona',  TRAINING_PERSONA_PROMPT_BASE),
    ]
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        for module, ptext in modules:
            exists = db.query(PromptVersion).filter_by(module=module, version='v1.0.0').first()
            if exists:
                continue
            db.add(PromptVersion(
                module=module,
                version='v1.0.0',
                prompt_text=ptext,
                is_active=True,
                changelog='Initial seed (Phase 04.7.1)',
            ))
        db.commit()
    finally:
        if owns_session:
            db.close()


_seed_prompt_versions()


def _seed_ewb_v2(db=None):
    """Phase 08 D-26: Seed 2 prompt_versions Rows fuer module='ewb'.

    Idempotent via existing-row-check. v1-legacy ist_default=True (Backward-
    Compat-Baseline), v2-modular ist_default=False (A/B-Herausforderer).

    Rufbar vom App-Startup (owns=True) oder aus Tests mit injizierter Session.
    """
    from database.db import SessionLocal
    from database.models import PromptVersion

    V1_LEGACY_TEXT = (
        "Du bist NERVE, ein Vertriebs-KI-Assistent im Live-Call.\n\n"
        "Wenn ein Einwand kommt, liefere EINE konkrete, sofort vorlesbare "
        "Gegenargumentation in 2-3 Saetzen. Kein Fachjargon, keine Floskeln "
        "wie 'Ich verstehe vollkommen'. Ende mit Gegenfrage.\n"
    )

    V2_MODULAR_TEXT = (
        "Du bist NERVE, ein Vertriebs-KI-Assistent im Live-Call.\n\n"
        "## Bausteine (Reihenfolge einhalten)\n"
        "1. ANKER: Kurz bestaetigen was der Kunde gesagt hat "
        "(kein 'Ich verstehe'-Floskel).\n"
        "2. REFRAME: Perspektivwechsel - stelle den Einwand in einen neuen Kontext.\n"
        "3. KERN-GEGENARGUMENT + BEWEIS: Ein konkretes Argument plus ein "
        "Beweis-Element (Zahlen, Fallstudie, Kundenzitat aus dem Profil).\n"
        "4. UEBERLEITUNG: Gegenfrage oder Alternativ-Close, "
        "der den Dialog zurueckholt.\n\n"
        "## Active Listening Block (D-47)\n"
        "- Reagiere auf konkrete Phrasen des Kunden, nicht auf Kategorien.\n"
        "- Wenn der Kunde korrigiert: korrigiere dich explizit "
        "('Danke fuer die Klarstellung, ...').\n"
        "- Wenn der Kunde ein Detail nennt: spiegele es zurueck "
        "bevor du argumentierst.\n"
        "- Bilde NIEMALS Hypothesen ueber Bedarf ohne Signal - frage nach.\n"
        "- Beachte Geschlechts-Hinweise im Vornamen und halte sie konsistent.\n\n"
        "## Harte Regeln\n"
        "- Max 45 Woerter pro Antwort.\n"
        "- NIEMALS apologetisch ('Ich verstehe, dass ...', 'Tut mir leid').\n"
        "- Anrede-Constraint aus Kontext-Block strikt einhalten.\n"
        "- Niemals Floskeln wie 'Das ist eine gute Frage'.\n"
    )

    owns = db is None
    if owns:
        db = SessionLocal()
    try:
        for version, ptext, is_default in [
            ('v1-legacy', V1_LEGACY_TEXT, True),
            ('v2-modular', V2_MODULAR_TEXT, False),
        ]:
            exists = (db.query(PromptVersion)
                      .filter_by(module='ewb', version=version)
                      .first())
            if exists:
                # Reconcile is_default vs. Plan 01 Block E backfill
                # (UPDATE ... SET is_default=1 WHERE is_active=1 setzt alle
                # ewb-Rows default=True beim App-Start — A/B-Semantik verlangt
                # aber genau 1 Default pro module). Fix: Seed-Flags als Source
                # of Truth bei jedem Start.
                if exists.is_default != is_default:
                    exists.is_default = is_default
                    print(f"[DB] Seed v08: reconciled ewb/{version}.is_default={is_default}")
                continue
            db.add(PromptVersion(
                module='ewb', version=version, prompt_text=ptext,
                is_active=True, is_default=is_default,
                changelog=f'Phase 08 Seed ({version})',
            ))
        db.commit()
        print("[DB] Seed v08: module='ewb' v1-legacy + v2-modular seeded (idempotent)")
    finally:
        if owns:
            db.close()


try:
    _seed_ewb_v2()
except Exception as e:
    print(f"[DB] _seed_ewb_v2 failed (non-fatal): {e}")


def _seed_ewb_scenarios(db=None):
    """Phase 08 Plan 06 D-34: Seed 3 Varianz-Test-Szenarien A/B/C als System-Training-Scenarios.

    Scenario A "Easy":          Standard-Einwand "Zu teuer" bei einfachem SaaS-Profil.
    Scenario B "Profil-reich":  Voll ausgefuelltes Profil mit branche_kontext + Bedarfs-Einwand.
    Scenario C "Edge-Case":     Multi-Einwand-Sequenz "Zu teuer" -> "Haben schon was".

    Idempotent via name-based existing-row-check.
    Rufbar vom App-Startup (owns=True) oder aus Tests mit injizierter Session.
    erstellt_von=NULL markiert System-Scenarios (Phase 04.9-Pattern).
    """
    from database.db import SessionLocal
    from database.models import TrainingScenario, Organisation
    import json as _json_seed

    scenarios = [
        {
            'name': '[P08-A] Varianz-Test Easy: Zu teuer',
            'beschreibung': ('Phase 08 Varianz-Test Scenario A. Standard-Einwand "Zu teuer" '
                             'gegen einen einfachen SaaS-Verkauf. Testet Baseline-Konsistenz '
                             'der EWB-Antworten ueber 5 Repeats.'),
            'kunde_situation': ('IT-Leiter eines KMU (40 Mitarbeiter) prueft eine SaaS-Loesung. '
                                'Budget ist knapp, Entscheidung steht kurz bevor.'),
            'kunde_verhalten': ('Skeptisch beim Preis. Will konkrete Kosten-Nutzen-Argumentation. '
                                'Vergleicht mit Wettbewerber-Angebot.'),
            'spezial_einwaende': ['Zu teuer'],
            'schwierigkeit': 'leicht',
        },
        {
            'name': '[P08-B] Varianz-Test Profil-reich: Bedarfs-Frage',
            'beschreibung': ('Phase 08 Varianz-Test Scenario B. Voll ausgefuelltes Profil mit '
                             'branche_kontext + eigene_formulierungen + beweise. '
                             'Testet ob tiefer Profil-Input konsistent in Antworten greift.'),
            'kunde_situation': ('Vertriebsleiter B2B-Software-Unternehmen. Aktuelle Tools funktionieren, '
                                'aber Team-Adoption stagniert. Hat bereits Alternativen evaluiert.'),
            'kunde_verhalten': ('Hinterfragt den Bedarf, zeigt aber Interesse an konkreten ROI-Zahlen. '
                                'Fragt nach Erfahrungswerten aus aehnlichen Branchen.'),
            'spezial_einwaende': ['Bedarf unklar', 'Zu teuer'],
            'schwierigkeit': 'mittel',
        },
        {
            'name': '[P08-C] Varianz-Test Edge-Case: Multi-Einwand-Sequenz',
            'beschreibung': ('Phase 08 Varianz-Test Scenario C. Multi-Einwand: "Zu teuer" '
                             'gefolgt von "Haben schon was Aehnliches". Testet Stabilitaet '
                             'der EWB-Pipeline bei Einwand-Kette ohne Kontext-Drift.'),
            'kunde_situation': ('Geschaeftsfuehrer Mittelstand. Nutzt Wettbewerber-Loesung seit 3 Jahren. '
                                'Prueft Wechsel, aber Migration-Kosten schrecken.'),
            'kunde_verhalten': ('Bringt schnell Einwand-Kette: erst Preis, dann Status-Quo-Bias. '
                                'Will gleichzeitig ueberzeugt werden dass Wechsel sich lohnt.'),
            'spezial_einwaende': ['Zu teuer', 'Haben schon was'],
            'schwierigkeit': 'schwer',
        },
    ]

    owns = db is None
    if owns:
        db = SessionLocal()
    try:
        # Hole erste Org (System-Scenarios haben erstellt_von=NULL, brauchen aber
        # org_id wegen NOT NULL-Constraint — Pattern aus Phase 04.9
        # _seed_system_training_scenarios Zeile 1280).
        first_org = db.query(Organisation).order_by(Organisation.id.asc()).first()
        if not first_org:
            print("[DB] Phase 08 _seed_ewb_scenarios skipped: no Organisation yet")
            return

        inserted = 0
        for s in scenarios:
            exists = db.query(TrainingScenario).filter_by(name=s['name']).first()
            if exists:
                continue
            ts = TrainingScenario(
                name=s['name'],
                beschreibung=s['beschreibung'],
                kunde_situation=s['kunde_situation'],
                kunde_verhalten=s['kunde_verhalten'],
                spezial_einwaende=_json_seed.dumps(s['spezial_einwaende'], ensure_ascii=False),
                schwierigkeit=s['schwierigkeit'],
                org_id=first_org.id,
                erstellt_von=None,  # System-Scenario (Phase 04.9-Marker)
            )
            db.add(ts)
            inserted += 1
        db.commit()
        if inserted:
            print(f"[DB] Phase 08 Seed: {inserted}/3 varianz-test scenarios (A/B/C) inserted")
        else:
            print("[DB] Phase 08 Seed: 3 varianz-test scenarios (A/B/C) already present")
    finally:
        if owns:
            db.close()


try:
    _seed_ewb_scenarios()
except Exception as e:
    print(f"[DB] _seed_ewb_scenarios failed (non-fatal): {e}")

# ── Audit-Log Immutable Trigger (Defense-in-Depth, nach create_all + migrate) ─
try:
    with engine.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS audit_log_no_update
            BEFORE UPDATE ON audit_log
            BEGIN
              SELECT RAISE(ABORT, 'audit_log is immutable');
            END;
        """)
        conn.exec_driver_sql("""
            CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
            BEFORE DELETE ON audit_log
            BEGIN
              SELECT RAISE(ABORT, 'audit_log is immutable');
            END;
        """)
        conn.commit()
        print("[DB] Audit-Log Trigger installed")
except Exception as e:
    print(f"[DB] Audit-Log Trigger setup failed: {e}")

# ── Plan definitions ──────────────────────────────────────────────────────────
PLANS = {
    'starter':  {'name': 'Starter',  'preis': 49, 'max_users': 1,
                 'minuten_limit': 1000, 'training_voice_limit': 50},
    'pro':      {'name': 'Pro',      'preis': 59, 'max_users': 1,
                 'minuten_limit': 1000, 'training_voice_limit': 50},
    'business': {'name': 'Business', 'preis': 69, 'max_users': 1,
                 'minuten_limit': 1000, 'training_voice_limit': 50},
}

# ── Data migrations (rename legacy records) ───────────────────────────────────
def _data_migrate():
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("UPDATE organisations SET name='NERVE Alpha' WHERE name='SalesNerve Alpha'"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("UPDATE organisations SET billing_email='admin@nerve.local' WHERE billing_email='andre@salesnerve.de'"))
            conn.commit()
            print('[DB] Migration: updated billing_email to admin@nerve.local')
        except Exception:
            pass

_data_migrate()

# ── Phase 08.19: JSON-Daten-Migration aller Profile auf schema_version=2 ─────
def _migrate_profile_json():
    """Idempotente Migration aller Profile auf Pydantic v2 ProfileSchema (schema_version=2).

    DB-Advisory-Lock verhindert Multi-Worker-Race-Condition beim Gunicorn-Multi-Worker-Start:
    - SQLite: isolation_level='EXCLUSIVE' (BEGIN EXCLUSIVE) — erste Worker haelt Exclusive-Lock
    - PostgreSQL: pg_advisory_xact_lock(819) — Lock bis Commit, dann idempotent skip
    Weitere Worker warten, pruefen schema_version (>= 2) und ueberspringen (idempotent).
    """
    import json as _json3
    from sqlalchemy import text as _text3
    try:
        from services.profile_schema import _migrate_profile_data as _mpd
    except ImportError as e:
        print(f"[Schema] _migrate_profile_json: import failed: {e}")
        return

    _db_url = str(engine.url)
    _is_sqlite = _db_url.startswith('sqlite')

    # DB-Advisory-Lock: Multi-Worker-Safety
    # SQLite: BEGIN EXCLUSIVE direkt als Statement (execution_options('EXCLUSIVE') nicht unterstuetzt)
    # PostgreSQL: pg_advisory_xact_lock(819) als erstes Statement in Transaktion
    with engine.connect() as conn:
        if _is_sqlite:
            try:
                conn.execute(_text3("BEGIN EXCLUSIVE"))
            except Exception as _e:
                print(f"[Schema] _migrate_profile_json: BEGIN EXCLUSIVE failed: {_e}")
                return
        else:
            try:
                conn.execute(_text3("SELECT pg_advisory_xact_lock(819)"))
            except Exception as _e:
                print(f"[Schema] _migrate_profile_json: pg_advisory_xact_lock failed: {_e}")
                return

        try:
            _rows = conn.execute(_text3("SELECT id, daten, consent_text FROM profiles")).fetchall()
        except Exception as e:
            print(f"[Schema] _migrate_profile_json: SELECT failed: {e}")
            return

        # ── Step A: Add type column to profile_opener (idempotent) ───────────────
        try:
            conn.execute(_text3("ALTER TABLE profile_opener ADD COLUMN type VARCHAR(20) NOT NULL DEFAULT 'opener'"))
            conn.commit()
            print("[DB] Migration: added profile_opener.type")
        except Exception:
            pass  # column already exists — idempotent

        # ── Step B: Backfill pitch rows inserted without type (name='Pitch' → type='pitch') ──
        try:
            conn.execute(_text3("UPDATE profile_opener SET type='pitch' WHERE name='Pitch' AND type='opener'"))
            conn.commit()
            print("[DB] Migration: backfilled profile_opener type='pitch' for Pitch rows")
        except Exception:
            pass

        for _row in _rows:
            _pid, _daten_str, _db_consent = _row[0], _row[1], _row[2]
            try:
                _daten = _json3.loads(_daten_str) if _daten_str else {}
            except Exception:
                _daten = {}

            # Idempotenz: schema_version >= 2 -> ueberspringen
            # None-safe: _daten.get() liefert None wenn Key=None — 'or 1' wandelt in 1 um
            if isinstance(_daten, dict) and (_daten.get('schema_version') or 1) >= 2:
                continue

            _opener_text = _daten.get('opener', '') if isinstance(_daten, dict) else ''
            _pitch_text  = _daten.get('pitch', '')  if isinstance(_daten, dict) else ''

            # ProfileOpener-Sync: SELECT-vor-INSERT (idempotent)
            try:
                _existing_opener = conn.execute(
                    _text3("SELECT COUNT(*) FROM profile_opener WHERE profile_id=:pid"),
                    {'pid': _pid}
                ).scalar()
                if _existing_opener == 0:
                    if _opener_text:
                        conn.execute(
                            _text3("INSERT INTO profile_opener (profile_id, name, inhalt, sortierung, type) VALUES (:pid, :name, :inhalt, 0, 'opener')"),
                            {'pid': _pid, 'name': 'Opener', 'inhalt': _opener_text}
                        )
                        conn.commit()
                        print(f"[Schema] Profil {_pid}: opener -> ProfileOpener synced")
                    if _pitch_text:
                        conn.execute(
                            _text3("INSERT INTO profile_opener (profile_id, name, inhalt, sortierung, type) VALUES (:pid, :name, :inhalt, 1, 'pitch')"),
                            {'pid': _pid, 'name': 'Pitch', 'inhalt': _pitch_text}
                        )
                        conn.commit()
                        print(f"[Schema] Profil {_pid}: pitch -> ProfileOpener synced")
            except Exception as _e:
                print(f"[Schema] Profil {_pid}: ProfileOpener sync failed: {_e}")

            # ── Step C: Migrate erlaubnis JSON field → ProfileOpener type='erlaubnis' ──
            _erlaubnis_text = _daten.get('erlaubnis', '') if isinstance(_daten, dict) else ''
            if _erlaubnis_text:
                try:
                    _existing_erlaubnis = conn.execute(
                        _text3("SELECT COUNT(*) FROM profile_opener WHERE profile_id=:pid AND type='erlaubnis'"),
                        {'pid': _pid}
                    ).scalar()
                    if _existing_erlaubnis == 0:
                        conn.execute(
                            _text3("INSERT INTO profile_opener (profile_id, name, inhalt, sortierung, type) VALUES (:pid, :name, :inhalt, 0, 'erlaubnis')"),
                            {'pid': _pid, 'name': 'Erlaubnisfrage', 'inhalt': _erlaubnis_text}
                        )
                        conn.commit()
                        print(f"[Schema] Profil {_pid}: erlaubnis -> ProfileOpener synced")
                except Exception as _e:
                    print(f"[Schema] Profil {_pid}: erlaubnis sync failed: {_e}")

            # consent_text dual-write (D-04): NULL explizit als leerer String (Finding 4)
            if not isinstance(_daten.get('meta'), dict):
                _daten['meta'] = {}
            if not _daten['meta'].get('consent_text'):
                _daten['meta']['consent_text'] = _db_consent or ''

            _daten = _mpd(_daten)

            try:
                _new_daten_str = _json3.dumps(_daten, ensure_ascii=False)
                conn.execute(
                    _text3("UPDATE profiles SET daten=:d WHERE id=:id"),
                    {'d': _new_daten_str, 'id': _pid}
                )
                conn.commit()
                print(f"[Schema] Profil {_pid}: migriert auf schema_version=2")
            except Exception as _e:
                print(f"[Schema] Profil {_pid}: UPDATE failed: {_e}")

# _migrate_profile_json() wird NACH _seed() und _seed_demo_profiles() aufgerufen
# (Zeile ~1877) — Profile muessen zuerst existieren bevor migriert werden kann.

# ── NERVE Vertrieb Profile ───────────────────────────────────────────────
NERVE_DEMO_PROFILE_JSON = json.dumps({
    "beschreibung": "NERVE ist ein KI-gestützter Live-Vertriebsassistent der während echten Verkaufsgesprächen live mithört, Einwände in Echtzeit erkennt und dem Berater sofort passende Gegenargumente, Coaching-Tipps und Kaufsignale auf den Bildschirm liefert. Kein Bot der dem Meeting beitritt — unsichtbar im Hintergrund, nur für den Berater sichtbar.",
    "produkt": "NERVE – Sales Intelligence live im Verkaufsgespräch. Unsichtbar, Echtzeit, nur für den Berater.",
    "preismodell": {
        "starter": {"preis": 49, "einheit": "User/Monat", "max_user": 5},
        "team": {"preis": 44, "einheit": "User/Monat", "max_user": 15},
        "business": {"preis": 39, "einheit": "User/Monat", "max_user": 30},
        "enterprise": {"preis": "individuell"},
        "testphase": "14 Tage, keine Kreditkarte nötig"
    },
    "usps": [
        "Unsichtbar im Hintergrund, kein störender Bot",
        "Tiefes Profil-System — vollständig anpassbar pro Branche",
        "Organisations-System mit Team-Verwaltung",
        "DSGVO-konform, deutsche Server",
        "Einwand-Erkennung + Berater-Coaching parallel",
        "Feedback-Loop für kontinuierliche Verbesserung"
    ],
    "konsequenz": "Jeder Monat ohne NERVE ist ein Monat mit vermeidbaren Einwänden die nicht behandelt werden. Abschlussquoten bleiben niedrig, neue Mitarbeiter brauchen Monate zum Einarbeiten, und der Konkurrent der NERVE nutzt schließt mehr ab.",
    "zielgruppe": {
        "alter": "28-50",
        "berufsstatus": "Vertriebsleiter, Geschäftsführer, Sales Manager, selbstständige Berater",
        "unternehmensgroesse": "Unternehmen mit 3-50 Vertriebsmitarbeitern",
        "branche": "SaaS, Finanzberatung, Versicherung, Consulting, Agentur",
        "vorwissen": "Mittel (kennen CRM, aber keine KI-Tools)",
        "entscheidungsverhalten": "Entscheidet nach ROI und Demo, oft mit Team",
        "schmerzpunkte": [
            "Neue Vertriebsmitarbeiter brauchen 6+ Monate bis sie produktiv sind",
            "Einwände kommen immer wieder gleich aber Antworten sind jedes Mal anders gut oder schlecht",
            "Abschlussquote stagniert obwohl das Team mehr Calls macht"
        ]
    },
    "schmerzpunkte": [
        {
            "situation": "Neue Vertriebsmitarbeiter brauchen 6+ Monate bis sie produktiv sind",
            "emotionaler_kern": "Angst vor verschwendetem Recruiting-Budget",
            "verstaerker": "Was kostet dich ein Mitarbeiter der 6 Monate braucht bis er seinen ersten Abschluss macht?"
        },
        {
            "situation": "Einwände kommen immer wieder gleich aber Antworten sind jedes Mal anders gut oder schlecht",
            "emotionaler_kern": "Frustration über inkonsistente Performance",
            "verstaerker": "Wie oft hörst du nach einem Call — hätte ich das mal anders gesagt?"
        },
        {
            "situation": "Abschlussquote stagniert obwohl das Team mehr Calls macht",
            "emotionaler_kern": "Gefühl dass mehr Aufwand nichts bringt",
            "verstaerker": "Mehr Calls lösen das Problem nicht wenn die Qualität der Gespräche gleich bleibt"
        }
    ],
    "emotionale_trigger": {
        "verlust_aversion": 9, "familie_verantwortung": 5, "status_anerkennung": 7,
        "zahlen_fakten": 9, "dringlichkeit": 8, "micro_commitments": 8
    },
    "phasen": [
        {"name": "Einstieg & Rapport", "beschreibung": "Vertrauen aufbauen, kurze persönliche Verbindung herstellen"},
        {"name": "Problem qualifizieren", "beschreibung": "Verstehen wie groß der Schmerz wirklich ist, in Zahlen ausdrücken"},
        {"name": "Demo vorbereiten", "beschreibung": "Erwartung setzen was sie gleich sehen werden"},
        {"name": "Live-Demo", "beschreibung": "Tool live zeigen, Kunde sieht sofort Mehrwert"},
        {"name": "Einwand-Behandlung", "beschreibung": "Alle offenen Fragen klären"},
        {"name": "Closing", "beschreibung": "Klare Entscheidung, nächster Schritt"}
    ],
    "einwaende_detail": [
        {"typ": "Kosten/Preis", "einwand": "Das ist uns zu teuer",
         "varianten": ["Das liegt über unserem Budget", "Können wir das günstiger bekommen?"],
         "gegenargument": "Verstanden. Was kostet euch aktuell ein Abschluss der nicht gemacht wird weil ein Einwand nicht richtig behandelt wurde? NERVE amortisiert sich oft nach dem ersten zusätzlichen Abschluss. Wie viele Abschlüsse macht dein Team pro Monat?",
         "technik": "Reframing auf ROI", "intensitaet": "Hoch"},
        {"typ": "Zeit/Aufschub", "einwand": "Wir haben gerade keine Zeit das einzuführen",
         "varianten": ["Das kommt zum falschen Zeitpunkt", "Lass uns das in Q2 nochmal anschauen"],
         "gegenargument": "Das kenne ich. Genau deshalb haben wir NERVE so gebaut dass ihr in unter 30 Minuten startet — kein IT-Projekt, kein langer Onboarding-Prozess. Was müsste sich ändern damit der Zeitpunkt passt?",
         "technik": "Vereinfachung + offene Frage", "intensitaet": "Mittel"},
        {"typ": "Vertrauen", "einwand": "Wir haben schon schlechte Erfahrungen mit KI-Tools gemacht",
         "varianten": ["Das haben wir schon mal probiert, hat nicht funktioniert"],
         "gegenargument": "Das höre ich oft. Was genau hat damals nicht funktioniert? NERVE unterscheidet sich weil es kein generisches Tool ist — ihr baut euer eigenes Profil mit euren Einwänden, eurer Sprache, eurem Prozess. Welcher Teil hat euch damals am meisten gefehlt?",
         "technik": "Differenzierung + Nachfrage", "intensitaet": "Hoch"},
        {"typ": "Kein Bedarf", "einwand": "Unser Team läuft gut, wir brauchen das nicht",
         "varianten": ["Wir haben unsere Prozesse im Griff"],
         "gegenargument": "Super — dann geht es nur darum wie ihr von gut auf exzellent kommt. Was wäre eure Abschlussquote wenn jeder eurer Mitarbeiter so abschließt wie euer bester?",
         "technik": "Aspirational framing", "intensitaet": "Mittel"},
        {"typ": "Entscheidungsträger", "einwand": "Das muss ich erst mit dem Team besprechen",
         "varianten": ["Ich entscheide das nicht alleine"],
         "gegenargument": "Absolut verständlich. Was brauchst du konkret damit du das intern gut vertreten kannst? Sollen wir einen kurzen Demo-Call mit den relevanten Personen machen?",
         "technik": "Enablement", "intensitaet": "Mittel"}
    ],
    "kaufsignale": [
        {"signal": "Wie lange dauert die Einrichtung?", "reaktion": "Sofort konkret werden — '30 Minuten, ich zeige es dir live. Wann passt es?'"},
        {"signal": "Könnt ihr das auch für unsere spezifische Branche anpassen?", "reaktion": "Ja bestätigen und direkt zeigen wie das Profil-System funktioniert"},
        {"signal": "Was passiert nach den 14 Tagen?", "reaktion": "Kaufsignal — direkt in Richtung Abschluss lenken"}
    ],
    "no_go": [
        "Unternehmen unter 3 Vertriebsmitarbeitern — ROI zu gering, falsche Zielgruppe",
        "Kein aktiver Telefonvertrieb oder kein Video-Call-Vertrieb — Produkt passt nicht",
        "Kein Budget unter 150€/Monat möglich — nicht verhandelbar"
    ],
    "wettbewerber": [
        {"name": "CloseAI", "schwaeche": "Kein transparentes Profil-System, Black Box für den Nutzer, kein Organisations-System", "unser_vorteil": "Vollständig anpassbares Profil, Team-Verwaltung, branchen-flexibel"},
        {"name": "CRM-Tools (HubSpot, Salesforce)", "schwaeche": "Kein Live-Coaching, nur Nachbereitung", "unser_vorteil": "Live im Gespräch, nicht danach"}
    ],
    "techniken": [
        {"name": "Reframing", "aktiv": True}, {"name": "Offene Fragen", "aktiv": True},
        {"name": "Verstärkung Schmerz", "aktiv": True}, {"name": "Micro-Commitments", "aktiv": True},
        {"name": "Soziale Bewährtheit", "aktiv": True}, {"name": "ROI-Rechnung", "aktiv": True}
    ],
    "verbotene_phrasen": ["Eigentlich", "Muss ich ehrlich sein", "Ich verstehe dass das teuer klingt", "Kein Problem"],
    "uebergaenge": [
        {"von": "Problem-Qualifizierung", "nach": "Live-Demo", "beschreibung": "Genau das zeige ich dir jetzt live — schau mal hier"}
    ],
    "ki": {
        "ton": "Direkt, auf Augenhöhe, keine Floskeln, konkret mit Zahlen wo möglich",
        "ansprache": "Du",
        "antwortlaenge": "2-3 Sätze, immer mit offener Gegenfrage",
        "sensitivitaet": "hoch",
        "zusatz": "NERVE verkauft sich über sich selbst. Wenn der Berater NERVE im Demo-Call nutzt während er NERVE verkauft, ist das der stärkste Beweis. Darauf immer hinweisen wenn passend."
    }
}, ensure_ascii=False)

# ── Seed initial account ──────────────────────────────────────────────────────
def _seed():
    db = get_session()
    try:
        if db.query(User).count() == 0:
            org = Organisation(
                name='NERVE Alpha',
                plan='starter',
                max_users=1,
                billing_email='admin@nerve.local',
                plan_preis=49,
            )
            db.add(org)
            db.flush()
            owner = User(
                org_id=org.id,
                email='admin@nerve.local',
                passwort_hash=generate_password_hash('SalesNerve2024!'),
                rolle='owner',
                vorname='André',
                nachname='Preuß',
                onboarding_done=True,
            )
            db.add(owner)
            db.flush()
            db.commit()
            print("[DB] Initial account created: admin@nerve.local")
        # Seed NERVE Vertrieb profile if missing
        _seed_demo_profile(db)
    finally:
        db.close()


def _seed_demo_profile(db):
    """Legt das NERVE Vertrieb Profil an, falls noch nicht vorhanden."""
    org = db.query(Organisation).filter_by(name='NERVE Alpha').first()
    if not org:
        return
    existing = db.query(Profile).filter_by(org_id=org.id, name='NERVE Vertrieb').first()
    if existing:
        return
    owner = db.query(User).filter_by(org_id=org.id, rolle='owner').first()
    profile = Profile(
        org_id=org.id,
        name='NERVE Vertrieb',
        branche='SaaS / KI-Software',
        daten=NERVE_DEMO_PROFILE_JSON,
        erstellt_von=owner.id if owner else None,
    )
    db.add(profile)
    db.flush()
    # Als Standard-Profil für den Owner setzen
    if owner and not owner.active_profile_id:
        owner.active_profile_id = profile.id
    db.commit()
    print("[DB] NERVE Vertrieb Profil erstellt und aktiviert.")

def _seed_demo_profiles():
    """Legt Demo-Trainingsprofile an falls noch nicht vorhanden."""
    db = get_session()
    try:
        org = db.query(Organisation).filter_by(name='NERVE Alpha').first()
        if not org:
            return
        demo_profiles = [
            ("IT-Dienstleister Demo", {
                "produkt": "Managed IT-Services und Cloud-Lösungen für mittelständische Unternehmen. Monatliche Pauschale ab 499€, inkl. Helpdesk, Monitoring und Backup.",
                "branche": "IT-Dienstleistung",
                "zielgruppe": {"position": "Geschäftsführer oder IT-Leiter", "unternehmen": "Mittelstand, 20-200 Mitarbeiter", "branche": "Verschiedene"},
                "einwaende_detail": [
                    {"typ": "Kosten/Preis", "einwand": "499€ im Monat ist zu viel", "gegenargument": "Was kostet euch ein Tag Systemausfall? Die meisten unserer Kunden rechnen mit 2.000-5.000€ pro Tag. Wie oft hattet ihr das letztes Jahr?"},
                    {"typ": "Vergleich", "einwand": "Wir haben schon einen IT-Dienstleister", "gegenargument": "Wie zufrieden seid ihr auf einer Skala von 1-10? Was müsste besser laufen?"},
                    {"typ": "Kein Bedarf", "einwand": "Unser interner ITler macht das", "gegenargument": "Was passiert wenn der mal krank ist oder kündigt? Wie schnell könntet ihr das auffangen?"},
                    {"typ": "Zeit/Aufschub", "einwand": "Wir sind gerade mitten in einem Projekt", "gegenargument": "Verstehe ich. Wann wäre ein guter Zeitpunkt für ein 15-minütiges Gespräch um zu schauen ob es überhaupt passt?"},
                    {"typ": "Entscheidungsträger", "einwand": "Das muss mein Chef entscheiden", "gegenargument": "Klar. Was bräuchte dein Chef um zu sagen: Ja, das schauen wir uns an?"},
                ],
                "phasen": [
                    {"name": "Einstieg", "beschreibung": "Kurze Vorstellung, Grund des Anrufs", "skript": ["Hallo [Name], hier ist [Berater] von [Firma].", "Ich rufe kurz an weil wir mittelständische Unternehmen in der Region bei ihrer IT unterstützen.", "Haben Sie kurz 2 Minuten?"]},
                    {"name": "Bedarfsanalyse", "beschreibung": "IT-Situation erfragen", "skript": ["Wie ist eure IT aktuell aufgestellt?", "Habt ihr einen internen ITler oder macht das jemand nebenbei?", "Was war euer letzter größerer IT-Vorfall?"]},
                    {"name": "Problemvertiefung", "beschreibung": "Schmerz aufdecken", "skript": ["Was passiert wenn ein System ausfällt — wie schnell seid ihr wieder online?", "Wie läuft das mit Backups und Datensicherung?"]},
                    {"name": "Lösungsvorstellung", "beschreibung": "Service erklären", "skript": ["Wir übernehmen das komplett: Monitoring, Helpdesk, Backup, Updates.", "Ab 499€ monatlich, alles inklusive, keine versteckten Kosten."]},
                    {"name": "Abschluss", "beschreibung": "Termin vereinbaren", "skript": ["Wie wäre es wenn ich mal bei euch vorbeikomme und mir die Infrastruktur anschaue?", "Passt euch nächste Woche Dienstag oder Donnerstag besser?"]},
                ],
                "kaufsignale": [
                    {"signal": "Wie schnell könntet ihr bei uns starten?", "reaktion": "Interesse an Timeline — konkretes Angebot machen"},
                    {"signal": "Habt ihr Referenzen aus unserer Branche?", "reaktion": "Konkretes Beispiel nennen, Vertrauen aufbauen"},
                ],
                "ki": {"ton": "Professionell aber bodenständig. Kein IT-Fachjargon. Sprich wie ein Berater der sich auskennt, nicht wie ein Techniker.", "zusatz": ""},
            }),
            ("Versicherungsmakler Demo", {
                "produkt": "Unabhängige Versicherungsberatung für Privatkunden. Schwerpunkt: Berufsunfähigkeit, private Krankenversicherung, Altersvorsorge. Honorar- und provisionsbasiert.",
                "branche": "Versicherung",
                "zielgruppe": {"position": "Privatperson oder Selbstständiger", "unternehmen": "", "branche": "Übergreifend"},
                "einwaende_detail": [
                    {"typ": "Kosten/Preis", "einwand": "Versicherungen sind mir zu teuer", "gegenargument": "Was wäre dir denn eine vernünftige Absicherung pro Monat wert? Oft geht es schon ab 30€ los."},
                    {"typ": "Kein Bedarf", "einwand": "Ich bin jung und gesund, brauche das nicht", "gegenargument": "Genau jetzt bekommst du die besten Konditionen. Was denkst du was passiert wenn du in 10 Jahren mit Vorerkrankungen anfragst?"},
                    {"typ": "Vertrauen", "einwand": "Versicherungen zahlen eh nie", "gegenargument": "Verstehe die Skepsis. Welche Erfahrung hast du konkret gemacht? Daran können wir anknüpfen."},
                    {"typ": "Zeit/Aufschub", "einwand": "Ich muss erstmal drüber nachdenken", "gegenargument": "Absolut. Worüber genau möchtest du nachdenken — über den Schutz oder über den Beitrag?"},
                    {"typ": "Vergleich", "einwand": "Ich habe schon einen Berater", "gegenargument": "Gut. Wann hat der zuletzt eure Verträge durchgeschaut und geprüft ob die noch passen?"},
                ],
                "phasen": [
                    {"name": "Begrüßung", "beschreibung": "Vertrauensaufbau, Anlass klären"},
                    {"name": "Lebenssituation", "beschreibung": "Familie, Beruf, Einkommen, Ziele erfragen"},
                    {"name": "Lückenanalyse", "beschreibung": "Bestehenden Schutz prüfen, Lücken aufzeigen"},
                    {"name": "Empfehlung", "beschreibung": "Passende Produkte vorstellen mit konkreten Zahlen"},
                    {"name": "Abschluss", "beschreibung": "Antrag vorbereiten oder Folgetermin vereinbaren"},
                ],
                "ki": {"ton": "Warm, empathisch, nicht aufdringlich. Der Kunde soll sich verstanden fühlen, nicht verkauft.", "zusatz": "Niemals Angst schüren. Immer sachlich bleiben und den Kunden selbst zur Erkenntnis führen."},
            }),
            ("Personalvermittlung Demo", {
                "produkt": "Personalvermittlung für Fach- und Führungskräfte im technischen Bereich. Erfolgsbasiert, keine Vorabkosten. Besetzungsquote 87%.",
                "branche": "Recruiting",
                "zielgruppe": {"position": "Geschäftsführer, HR-Leiter, Abteilungsleiter", "unternehmen": "Mittelstand und Industrie", "branche": "Technik, Produktion, Engineering"},
                "einwaende_detail": [
                    {"typ": "Kosten/Preis", "einwand": "Die Provision ist zu hoch", "gegenargument": "Was kostet euch eine unbesetzte Stelle pro Monat? Die meisten rechnen mit 3.000-8.000€ an entgangenem Umsatz und Mehrbelastung."},
                    {"typ": "Kein Bedarf", "einwand": "Wir machen das über Stellenanzeigen", "gegenargument": "Wie viele Bewerbungen bekommt ihr pro Anzeige? Und wie viele davon sind wirklich qualifiziert?"},
                    {"typ": "Vergleich", "einwand": "Wir arbeiten schon mit einem anderen Personalberater", "gegenargument": "Wie lange ist die Stelle schon offen? Wir arbeiten erst wenn wir liefern — kein Risiko für euch."},
                    {"typ": "Vertrauen", "einwand": "Personalberater schicken oft unpassende Kandidaten", "gegenargument": "Genau deswegen machen wir erstmal ein Briefing mit euch. Was muss der Kandidat konkret können?"},
                    {"typ": "Zeit/Aufschub", "einwand": "Wir stellen gerade nicht ein", "gegenargument": "Verstehe. Wie sieht eure Personalplanung für die nächsten 6 Monate aus?"},
                ],
                "phasen": [
                    {"name": "Einstieg", "beschreibung": "Vorstellung und Anlass"},
                    {"name": "Bedarfsermittlung", "beschreibung": "Offene Stellen, Anforderungen, Timeline"},
                    {"name": "Problemvertiefung", "beschreibung": "Kosten der Nichtbesetzung, bisherige Versuche"},
                    {"name": "Lösung", "beschreibung": "Prozess erklären, Erfolgsquote, keine Vorabkosten"},
                    {"name": "Commitment", "beschreibung": "Briefing-Termin vereinbaren"},
                ],
                "ki": {"ton": "Direkt, geschäftlich, auf den Punkt. Kein Smalltalk. Vertriebler reden mit beschäftigten Entscheidern.", "zusatz": ""},
            }),
        ]
        for name, daten in demo_profiles:
            existing = db.query(Profile).filter_by(org_id=org.id, name=name).first()
            if not existing:
                p = Profile(
                    org_id=org.id,
                    name=name,
                    branche=daten.get('branche', ''),
                    daten=json.dumps(daten, ensure_ascii=False),
                )
                db.add(p)
                print(f"[DB] Demo-Profil '{name}' erstellt")
        db.commit()
    finally:
        db.close()


def _seed_training_scenarios():
    """Legt Standard-Trainingsszenarien für die erste Organisation an."""
    from database.models import TrainingScenario
    db = get_session()
    try:
        org = db.query(Organisation).first()
        if not org:
            return
        if db.query(TrainingScenario).filter_by(org_id=org.id).count() > 0:
            return

        _j = json.dumps
        szenarien = [
            # ── LEICHT ──────────────────────────────────────────────────────
            TrainingScenario(
                org_id=org.id, schwierigkeit='leicht',
                name='Warmer Lead — hat Infos angefordert',
                beschreibung='Der Kunde hat über die Website Infos angefordert und erwartet deinen Anruf. Grundsätzlich offen.',
                kunde_situation='Hat letzte Woche ein Whitepaper heruntergeladen und seine Nummer hinterlassen. Weiß dass jemand anruft. Ist neugierig aber hat noch keine Dringlichkeit.',
                kunde_verhalten='Freundlich, stellt Fragen, lässt sich erklären. Bringt 1-2 leichte Einwände die eher Rückfragen sind.',
                spezial_einwaende=_j(['Klingt interessant, aber was kostet das genau?','Ich muss das erstmal mit meinem Kollegen besprechen'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='leicht',
                name='Empfehlung von Bestandskunde',
                beschreibung='Ein zufriedener Kunde hat den Kontakt weitergegeben. Vertrauensvorschuss vorhanden.',
                kunde_situation='Sein Geschäftspartner nutzt dein Produkt bereits und hat es empfohlen. Weiß grob worum es geht. Hat 10 Minuten Zeit.',
                kunde_verhalten='Offen und interessiert weil die Empfehlung von jemandem kommt dem er vertraut. Will wissen was es konkret für ihn bringt.',
                spezial_einwaende=_j(['Mein Geschäftspartner ist begeistert, aber unsere Situation ist etwas anders','Können Sie mir erstmal was schriftlich schicken?'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='leicht',
                name='Follow-up nach Demo',
                beschreibung='Der Kunde hat letzte Woche eine Demo gesehen. Du rufst nach um zu fragen wie es weitergeht.',
                kunde_situation='Hat die Demo gesehen und fand sie gut, hat aber noch nicht entschieden. Wartet eigentlich darauf dass du dich meldest.',
                kunde_verhalten='Positiv gestimmt, hat ein paar Detailfragen. Braucht einen kleinen Schubs zum nächsten Schritt.',
                spezial_einwaende=_j(['Die Demo war gut, aber ich habe noch ein paar Fragen','Wir vergleichen gerade noch mit einer anderen Lösung'], ensure_ascii=False),
                erstellt_von=None,
            ),
            # ── MITTEL ──────────────────────────────────────────────────────
            TrainingScenario(
                org_id=org.id, schwierigkeit='mittel',
                name='Kaltakquise — Geschäftsführer KMU',
                beschreibung='Klassische Kaltakquise. Der Kunde kennt dich nicht und hat nicht auf deinen Anruf gewartet.',
                kunde_situation='Leitet ein Unternehmen mit 25 Mitarbeitern. Hat ein vages Problem das dein Produkt löst, ist sich dessen aber nicht bewusst. Gestresst und wenig Zeit.',
                kunde_verhalten='Skeptisch aber höflich. Gibt dir 2 Minuten. Stellt kritische Fragen. Sagt "Schicken Sie mir mal was zu" als Standardabwehr.',
                spezial_einwaende=_j(['Schicken Sie mir eine Email, ich schaue mir das an','Wir haben dafür gerade kein Budget','Wie sind Sie an meine Nummer gekommen?','Wir sind da eigentlich gut aufgestellt'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='mittel',
                name='Wettbewerber-Wechsel — Kunde nutzt Konkurrenz',
                beschreibung='Der Kunde nutzt bereits ein Konkurrenzprodukt. Du musst ihn überzeugen zu wechseln.',
                kunde_situation='Nutzt seit 2 Jahren ein Wettbewerbsprodukt. Ist nicht unzufrieden, sieht aber Verbesserungspotential. Hat keinen akuten Handlungsdruck.',
                kunde_verhalten='Vergleicht aktiv und detailliert. Fragt nach konkreten Unterschieden und ROI. Kennt sich aus und lässt sich nicht mit Floskeln abspeisen.',
                spezial_einwaende=_j(['Wir nutzen seit 2 Jahren Produkt X und sind eigentlich zufrieden','Ein Wechsel wäre mit viel Aufwand verbunden','Was können Sie was Produkt X nicht kann?','Wir haben gerade einen Jahresvertrag laufen'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='mittel',
                name='Preisverhandlung — Kunde will Rabatt',
                beschreibung='Der Kunde ist grundsätzlich interessiert, versucht aber den Preis zu drücken.',
                kunde_situation='Hat die Demo gesehen, findet das Produkt gut, aber behauptet das Budget sei knapp. Will verhandeln und testet wie weit du runtergehst.',
                kunde_verhalten='Strategisch. Nennt einen günstigeren Wettbewerber. Fragt nach Rabatt, längerer Testphase, oder weniger Features für weniger Geld. Blufft teilweise.',
                spezial_einwaende=_j(['Euer Wettbewerber bietet das Gleiche für 30% weniger','Wenn ihr beim Preis nicht entgegenkommt können wir nicht starten','Können wir erstmal mit einer abgespeckten Version starten?','Für das Budget müsste ich meinen CFO überzeugen'], ensure_ascii=False),
                erstellt_von=None,
            ),
            # ── SCHWER ──────────────────────────────────────────────────────
            TrainingScenario(
                org_id=org.id, schwierigkeit='schwer',
                name='Abwimmler — will das Gespräch beenden',
                beschreibung='Der Kunde hat keine Lust zu reden und versucht dich schnell loszuwerden.',
                kunde_situation='Wurde kalt angerufen, ist genervt, hat schlechte Erfahrungen mit Vertrieblern. Will auflegen.',
                kunde_verhalten='Kurz angebunden, unterbricht dich, gibt dir maximal 30 Sekunden. Sagt sofort "Kein Interesse". Nur wenn du in den ersten 10 Sekunden etwas wirklich Relevantes sagst hört er weiter zu.',
                spezial_einwaende=_j(['Kein Interesse, danke','Rufen Sie mich bitte nicht mehr an','Ich habe gerade absolut keine Zeit','Wir brauchen sowas nicht','Woher haben Sie meine Nummer?'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='schwer',
                name='Technischer Entscheider — will Details',
                beschreibung='Ein CTO oder IT-Leiter der extrem detaillierte technische Fragen stellt.',
                kunde_situation='Technisch versiert, hat dein Produkt bereits recherchiert, kennt die Schwächen. Will wissen ob du dein eigenes Produkt wirklich verstehst.',
                kunde_verhalten='Stellt Fangfragen zu Architektur, Datenschutz, Integrationen, SLAs. Entlarvt Floskeln sofort. Respektiert nur ehrliche Antworten.',
                spezial_einwaende=_j(['Wo stehen eure Server und wer hat Zugriff auf die Daten?','Welche API-Schnittstellen bietet ihr an?','Was passiert bei einem Ausfall — habt ihr SLAs?','Das Feature klingt gut in der Theorie, aber wie sieht das in der Praxis aus?','Euer Wettbewerber hat da eine bessere Lösung'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='schwer',
                name='Einkäufer — reiner Preisfokus',
                beschreibung='Du sprichst nicht mit dem Nutzer sondern mit dem Einkäufer dem nur der Preis wichtig ist.',
                kunde_situation='Der Fachbereich will dein Produkt, aber der Einkäufer muss zustimmen. Ihm ist die Funktion egal, er will den besten Preis und hat 3 Angebote auf dem Tisch.',
                kunde_verhalten='Emotionslos, sachlich, drückt auf jeden Cent. Droht mit Wettbewerb. Fragt nach Staffelpreisen, Vertragslaufzeiten, Skonti. Lässt sich nicht emotional abholen.',
                spezial_einwaende=_j(['Ich habe hier drei Angebote liegen, ihr seid die teuersten','Bei Anbieter X bekommen wir 24 Monate zum Preis von 18','Ohne 15% Rabatt kann ich das nicht freigeben','Können Sie mir das als Jahreslizenz statt monatlich anbieten?','Der Fachbereich findet Sie gut, aber ich entscheide über das Budget'], ensure_ascii=False),
                erstellt_von=None,
            ),
            # ── SEKRETÄRIN ──────────────────────────────────────────────────
            TrainingScenario(
                org_id=org.id, schwierigkeit='sekretaerin',
                name='Sekretärin blockt — Chef ist Meeting-König',
                beschreibung='Die Sekretärin ist professionell und blockt jeden ab der keinen Termin hat. Der Chef dahinter ist interessiert aber schwer zu erreichen.',
                kunde_situation='Der Chef ist tatsächlich viel in Meetings und die Sekretärin filtert konsequent. Aber wenn du es schaffst durchzukommen, ist der Chef offen für ein kurzes Gespräch.',
                kunde_verhalten='Sekretärin: Professionell, fragt warum du anrufst, bietet Email an, sagt Chef ist nicht erreichbar. Stellt nur durch wenn du einen überzeugenden Grund nennst. Chef: Direkt, wenig Zeit, will in 60 Sekunden wissen warum er zuhören soll.',
                spezial_einwaende=_j(['Herr Müller ist den ganzen Tag in Meetings','Können Sie mir eine Email schicken? Ich leite das weiter','Worum geht es denn konkret?','Haben Sie einen Termin?'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='sekretaerin',
                name='Sekretärin ist die Entscheiderin',
                beschreibung='Die Assistentin hat mehr Einfluss als du denkst. Sie ist die eigentliche Gatekeeperin UND Beraterin des Chefs.',
                kunde_situation='Die Assistentin filtert nicht nur Anrufe sondern berät den Chef auch bei Entscheidungen. Wenn sie sagt "Das ist nichts für uns" ist das quasi ein Veto.',
                kunde_verhalten='Sekretärin: Stellt intelligente Fragen, will verstehen was du anbietest, bildet sich eine eigene Meinung. Wenn du SIE überzeugst empfiehlt sie dich dem Chef.',
                spezial_einwaende=_j(['Erklären Sie mir doch mal kurz was genau Sie anbieten','Und was unterscheidet Sie von den anderen die hier jede Woche anrufen?','Ich kann Ihnen nicht versprechen dass er zurückruft','Wissen Sie, wir bekommen solche Anrufe täglich'], ensure_ascii=False),
                erstellt_von=None,
            ),
        ]
        for s in szenarien:
            db.add(s)
        db.commit()
        print(f"[DB] {len(szenarien)} Standard-Trainingsszenarien erstellt")
    finally:
        db.close()


def _seed_system_training_scenarios():
    """Phase 04.9: Legt 7 DACH-B2B System-Trainingsszenarien an (erstellt_von=NULL als Systemmarker)."""
    from database.models import TrainingScenario
    db = get_session()
    try:
        org = db.query(Organisation).first()
        if not org:
            return
        # Idempotent: skip if any system scenarios already exist (erstellt_von IS NULL)
        existing = db.query(TrainingScenario).filter(TrainingScenario.erstellt_von == None, TrainingScenario.name == 'SaaS-Vertrieb: Cloud-Migration').first()
        if existing:
            return

        _j = json.dumps
        system_szenarien = [
            TrainingScenario(
                org_id=org.id, schwierigkeit='mittel',
                name='SaaS-Vertrieb: Cloud-Migration',
                beschreibung='Mittelständischer IT-Leiter prüft Cloud-Lösungen für seine On-Premise-Infrastruktur. Kosten, Sicherheit und Migration sind die zentralen Themen.',
                kunde_situation='IT-Leiter in einem Produktionsunternehmen mit 80 Mitarbeitern. Aktuelle Server sind veraltet, Budget für Neuanschaffung wurde genehmigt. Prüft gerade 3 Cloud-Anbieter.',
                kunde_verhalten='Technisch versiert, fragt nach Details zu Datensicherheit und Migration. Hat Bedenken wegen Ausfallzeiten. Braucht gute Argumente für den Geschäftsführer.',
                spezial_einwaende=_j(['Unsere Daten liegen sensibel, wir können nicht einfach in die Cloud', 'Was passiert bei einem Ausfall?', 'Der Migrationaufwand klingt enorm'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='mittel',
                name='Maschinenbau: Automatisierungslösung',
                beschreibung='Produktionsleiter sucht Effizienzsteigerung durch Automatisierung. ROI und Implementierungszeit sind entscheidend.',
                kunde_situation='Produktionsleiter in einem Maschinenbauunternehmen mit 150 Mitarbeitern. Hat manuelle Prozesse die Fehler und Verzögerungen verursachen. Sein Chef hat Druck wegen Lieferterminen.',
                kunde_verhalten='Pragmatisch, will konkrete Zahlen zum ROI. Skeptisch gegenüber langen Implementierungszeiten. Fragt nach Referenzen aus der Branche.',
                spezial_einwaende=_j(['Wir haben das schon mal probiert und es hat nicht funktioniert', 'Wie lange dauert die Implementierung realistisch?', 'Was kostet das in der Gesamtkalkulation?'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='mittel',
                name='Versicherung: Betriebliche Altersvorsorge',
                beschreibung='Geschäftsführer 50+ evaluiert betriebliche Altersvorsorge für sein Team. Steuervorteile und Mitarbeiterbindung sind Hauptmotive.',
                kunde_situation='Inhaber eines Handwerksbetriebs mit 12 Mitarbeitern. Hat gerade einen Mitarbeiter durch bessere bAV beim Wettbewerber verloren. Will das Thema jetzt angehen aber ist sich unsicher.',
                kunde_verhalten='Fragt viel nach steuerlichen Aspekten, will keine Komplexität. Bedenken wegen Verwaltungsaufwand und Haftung. Vertraut dem Berater erst nach Referenzen.',
                spezial_einwaende=_j(['Das ist mir zu komplex, ich habe keinen Steuerberater der sich auskennt', 'Was ist wenn ein Mitarbeiter kündigt?', 'Ich kenne da schon jemanden der das macht'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='leicht',
                name='Immobilien: Gewerbeflächen-Vermittlung',
                beschreibung='Expandierendes Startup sucht neue Büroflächen. Flexibilität und günstige Konditionen sind Priorität.',
                kunde_situation='CEO eines Series-A-Startups mit 25 Mitarbeitern. Aktuelles Büro wird zu klein, sucht in 3 Monaten neue Flächen. Hat schon erste Angebote eingeholt.',
                kunde_verhalten='Offen und gesprächsbereit, will aber flexible Mietlösungen. Vergleicht aktiv mehrere Angebote. Entscheidet gemeinsam mit Co-Founder.',
                spezial_einwaende=_j(['Wir brauchen maximale Flexibilität, kein 5-Jahres-Vertrag', 'Haben Sie auch Flächen mit Ausbauoption?'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='schwer',
                name='Dienstleistung: IT-Security Audit',
                beschreibung='CFO nach Datenleck evaluiert Security-Partner. Vertrauen und Expertise müssen erst bewiesen werden.',
                kunde_situation='CFO eines Finanzdienstleisters der vor 3 Monaten einen Datenleck hatte. Ist intern unter Druck, will jetzt schnell handeln aber die falsche Wahl kostet ihn den Job.',
                kunde_verhalten='Sehr skeptisch und vorsichtig. Prüft jeden Punkt genau. Fragt nach Zertifizierungen, Referenzen und konkreter Vorgehensweise. Kein Spielraum für vage Antworten.',
                spezial_einwaende=_j(['Warum sollte ich Ihnen vertrauen? Ich kenne Sie nicht', 'Was ist Ihre ISO-Zertifizierung?', 'Wie läuft das ab wenn Sie Schwachstellen finden?', 'Mein letzter Dienstleister hat versagt'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='mittel',
                name='SaaS-Vertrieb: CRM-Wechsel',
                beschreibung='Vertriebsleiter unzufrieden mit aktuellem CRM aber wechselscheu. Migration und Teamakzeptanz sind die größten Hürde.',
                kunde_situation='Vertriebsleiter in einem B2B-Software-Unternehmen. Nutzt seit 4 Jahren ein altes CRM das schlecht integriert. Team klagt, aber alle Wechselversuche sind bisher gescheitert.',
                kunde_verhalten='Interessiert aber müde von gescheiterten Projekten. Fragt konkret nach Migrationsunterstützung und Onboarding. Will einen Piloten mit 3 Leuten vor dem Rollout.',
                spezial_einwaende=_j(['Wir haben das schon dreimal versucht, das Team zieht nie mit', 'Was passiert mit unseren 4 Jahre alten CRM-Daten?', 'Wie lange dauert das Onboarding realistisch?'], ensure_ascii=False),
                erstellt_von=None,
            ),
            TrainingScenario(
                org_id=org.id, schwierigkeit='leicht',
                name='Maschinenbau: Wartungsvertrag',
                beschreibung='Werkleiter will Ausfallzeiten reduzieren und sucht prädiktiven Wartungsvertrag. Preis-Leistung ist entscheidend.',
                kunde_situation='Werkleiter in einem Metallverarbeitungsbetrieb. Hatte letztes Jahr zwei ungeplante Maschinenausfälle die je 50.000 Euro Schaden verursachten. Jetzt offen für präventive Lösungen.',
                kunde_verhalten='Offen und pragmatisch. Hat das Problem bereits beziffert. Fragt nach konkreten Leistungen und Reaktionszeiten. Entscheidet relativ schnell wenn das Preis-Leistungs-Verhältnis stimmt.',
                spezial_einwaende=_j(['Was ist in dem Wartungsvertrag konkret enthalten?', 'Wie schnell sind Sie vor Ort wenn etwas ist?'], ensure_ascii=False),
                erstellt_von=None,
            ),
        ]
        for s in system_szenarien:
            db.add(s)
        db.commit()
        print(f"[DB] {len(system_szenarien)} DACH-System-Trainingsszenarien erstellt")
    finally:
        db.close()


def _seed_changelog():
    """Legt initiale Changelog-Einträge an."""
    db = get_session()
    try:
        if db.query(Changelog).count() == 0:
            import json as _j
            entries = [
                Changelog(
                    version='0.9.0',
                    titel='Erster funktionsfähiger Build',
                    inhalt='• Live-Einwandbehandlung mit 2 Gegenargumenten\n• Vorwand vs. echter Einwand Erkennung\n• Sprachanalyse: Redeanteil, Tempo, Monolog\n• Quick-Action Buttons\n• Post-Call Analyse mit Skript-Abdeckung\n• Team-Verwaltung mit Einladungssystem\n• Kaufbereitschafts-Tracking in Echtzeit',
                    typ='major',
                    created_at=datetime(2026, 3, 26),
                ),
                Changelog(
                    version='0.9.1',
                    titel='Rebranding auf NERVE',
                    inhalt='• Neues Logo: N-Mark + NERVE Wortmarke\n• Neue Farben: Gold + Navy\n• Alle Templates aktualisiert\n• Profil-Injektion in Claude-Calls\n• Google Fonts Integration (Playfair + DM Sans)',
                    typ='improvement',
                    created_at=datetime(2026, 3, 27),
                ),
                Changelog(
                    version='0.9.2',
                    titel='Trainingsmodus mit KI-Stimme',
                    inhalt='• KI-Kunde antwortet mit echter Stimme (ElevenLabs)\n• Einwahlbildschirm mit deutschem Freizeichen\n• Sekretärin-Modus als Schwierigkeitsstufe\n• 4 Schwierigkeitsgrade: Leicht bis Sekretärin+Chef\n• Scoring nach jedem Training (5 Kategorien)\n• Eigene Trainingsszenarien erstellen\n• Mehrsprachig: 9 Sprachen mit länderspezifischem Freizeichen\n• Hilfe-Button für Antwortvorschläge',
                    typ='feature',
                    bekannte_bugs=_j.dumps([
                        {'bug': 'Audio startet nicht automatisch auf iOS Safari',
                         'workaround': 'Tippe einmal auf den Play-Button — iOS blockiert Autoplay'},
                        {'bug': 'Bei langsamer Verbindung kann die KI-Antwort bis zu 5 Sekunden dauern',
                         'workaround': 'Das ist normal — die KI generiert eine durchdachte Antwort'},
                    ], ensure_ascii=False),
                    created_at=datetime(2026, 3, 28),
                ),
            ]
            for e in entries:
                db.add(e)
            db.commit()
            print("[DB] Changelog Seed-Daten eingefügt")
    finally:
        db.close()


_seed()
# _seed_demo_profiles()  # 2026-04-28 deaktiviert (Andre): nutzlose System-Demos aus früher Phase, werden in Phase 08.22 durch echte Branchen-Templates mit Wisdom-Vorbefüllung ersetzt
_migrate_profile_json()   # nach Seed: alle Profile existieren, jetzt migrieren
_seed_training_scenarios()
_seed_system_training_scenarios()
# Phase 08.19.4 D-04: _load_initial_profile() geloescht — war DSGVO-Verstoss
# (hardcoded single-tenant global). Profil wird jetzt pro SID in
# start_live_session via init_session_state() + set_profile_for_sid() geladen.
_seed_changelog()

# ── Register blueprints ───────────────────────────────────────────────────────
from routes.auth          import auth_bp
from routes.organisations  import orgs_bp
from routes.profiles       import profiles_bp
from routes.app_routes     import app_routes_bp
from routes.dashboard      import dashboard_bp
from routes.logs_routes    import logs_bp
from routes.training       import training_bp
from routes.coach          import coach_bp
from routes.onboarding     import onboarding_bp
from routes.settings       import settings_bp
from routes.waitlist       import waitlist_bp
from routes.changelog      import changelog_bp
from routes.payments       import payments_bp
from routes.legal          import legal_bp
from routes.performance    import performance_bp
from routes.oauth          import oauth_bp, init_oauth
from routes.feedback       import feedback_bp
from routes.admin_dashboard import admin_dashboard_bp
from routes.learning       import learning_bp
# Phase 08 Plan 06:
from routes.admin_ewb      import admin_ewb_bp

app.register_blueprint(feedback_bp)
app.register_blueprint(admin_dashboard_bp)
app.register_blueprint(admin_ewb_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(orgs_bp)
app.register_blueprint(profiles_bp)
app.register_blueprint(app_routes_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(training_bp)
app.register_blueprint(coach_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(waitlist_bp)
app.register_blueprint(changelog_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(legal_bp)
app.register_blueprint(performance_bp)
app.register_blueprint(oauth_bp)
app.register_blueprint(learning_bp)
init_oauth(app)

# ── CSRF-Exempts für externe Endpoints ────────────────────────────────────────
# stripe_webhook: Stripe-Server POSTen direkt — kein Browser-Cookie, Stripe signiert via
# STRIPE_WEBHOOK_SECRET. CSRF-Schutz hier wäre falsch-positiv und würde Webhooks brechen.
# google_callback / microsoft_callback: OAuth GET-Callbacks — kein Browser-POST, kein CSRF-Risiko.
from routes.payments import stripe_webhook
from routes.oauth import google_callback, microsoft_callback
csrf.exempt(stripe_webhook)
csrf.exempt(google_callback)
csrf.exempt(microsoft_callback)

# ── Global before_request: populate g.user for all routes (incl. Flask-Admin) ─
@app.before_request
def _load_user():
    from flask import session as _sess, g as _g2
    uid = _sess.get('user_id')
    if uid is None:
        return
    if getattr(_g2, 'user', None) is not None:
        return  # already set by login_required
    from database.db import get_session as _get_sess
    from database.models import User as _User, Organisation as _Org
    db = _get_sess()
    try:
        user = db.get(_User, uid)
        if user and user.aktiv:
            _g2.user = user
            _g2.org  = db.get(_Org, user.org_id)
    finally:
        db.close()

# ── Favicon stub (POLISH-17) ──────────────────────────────────────────────────
# Browser requesten /favicon.ico automatisch — ohne Datei/Route schlug es in einen
# 500er mit Traceback um, weil die Exception am errorhandler unten landete.
# 204 No Content beendet den Request sauber und verhindert Console-/Log-Noise.
# TODO: Echtes NERVE-Icon in static/favicon.ico ablegen und hier via send_from_directory servieren.
@app.route('/favicon.ico')
def favicon():
    return '', 204

# ── Global JSON Error Handler ─────────────────────────────────────────────────
# Returns full traceback as JSON for API endpoints instead of HTML 500 page
import traceback as _tb
from flask import request as _request
from werkzeug.exceptions import HTTPException as _HTTPException

@app.errorhandler(500)
def _handle_500(e):
    tb_str = _tb.format_exc()
    print(tb_str)  # Server-side logging BLEIBT
    if (_request.content_type and 'json' in _request.content_type) or _request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': False, 'error': 'internal server error'}), 500
    return '', 500

@app.errorhandler(Exception)
def _handle_exception(e):
    # Wave 4 / POLISH-21: HTTPException-Passthrough MUSS als erste Zeile stehen,
    # bevor Logging/Traceback-Rendering. Werkzeug-HTTPExceptions (404, 403, 405 …)
    # tragen ihren Statuscode selbst und sollen Flasks normales Rendering bekommen —
    # sonst landen 404er im generischen 500-Handler mit Traceback im Browser
    # (Security-Leak: Server-Code sichtbar).
    if isinstance(e, _HTTPException):
        return e
    tb_str = _tb.format_exc()
    print(tb_str)  # Server-side logging BLEIBT
    if (_request.content_type and 'json' in _request.content_type) or _request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': False, 'error': 'Internal Server Error'}), 500
    return '', 500

# ── Flask-Admin (Superadmin only, gated via SecureIndexView) ─────────────────
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.theme import Bootstrap4Theme
from flask import g as _g, redirect as _redirect, url_for as _url_for, abort as _abort
from database.db import db_session as _db_session

class SecureIndexView(AdminIndexView):
    def is_accessible(self):
        return getattr(_g, 'user', None) is not None and getattr(_g.user, 'is_superadmin', False)
    def inaccessible_callback(self, name, **kwargs):
        if getattr(_g, 'user', None) is None:
            return _redirect(_url_for('auth.login'))
        _abort(403)

admin = Admin(
    app,
    name='NERVE Admin',
    theme=Bootstrap4Theme(),
    index_view=SecureIndexView(url='/admin'),
)

# ── Flask-Admin ModelViews + CustomViews ──────────────────────────────────────
from routes.admin_views import (
    UserAdmin, OrgAdmin, FeedbackAdmin, AuditLogAdmin, ConvLogAdmin,
    KpiDashboardView, PlanningListView, CrmView, register_admin_screenshot_route,
)
from database.models import Feedback as _Feedback, AuditLog as _AuditLog, ConversationLog as _ConvLog

admin.add_view(KpiDashboardView(name='KPI', endpoint='kpi', url='/admin/kpi'))
admin.add_view(PlanningListView(name='Planung', endpoint='planning', url='/admin/planning'))
admin.add_view(CrmView(name='CRM', endpoint='crm_view', url='/admin/crm'))
admin.add_view(FeedbackAdmin(_Feedback, _db_session, name='Feedback', endpoint='feedback_admin'))
admin.add_view(UserAdmin(User, _db_session, name='Users'))
admin.add_view(OrgAdmin(Organisation, _db_session, name='Orgs'))
admin.add_view(ConvLogAdmin(_ConvLog, _db_session, name='Sessions', category='Logs'))
admin.add_view(AuditLogAdmin(_AuditLog, _db_session, name='Audit', category='Logs'))
register_admin_screenshot_route(app)

# ── Share socketio with services ──────────────────────────────────────────────
# Patch extensions module so services can import socketio
import extensions as _ext
_ext.socketio = socketio

# ── Start background threads ──────────────────────────────────────────────────
from services.deepgram_service import register_audio_handlers
from services.claude_service   import analyse_loop, coaching_loop

register_audio_handlers(socketio)
threading.Thread(target=analyse_loop,     daemon=True).start()
threading.Thread(target=coaching_loop,    daemon=True).start()

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 55)
    print("  NERVE – Sales Intelligence · Live STT + KI")
    print("  http://localhost:5000")
    print("=" * 55)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
