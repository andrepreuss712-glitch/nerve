import json
import logging
import os
import threading
from datetime import datetime
from flask import Flask
from flask_socketio import SocketIO
from config import SECRET_KEY, CORS_ORIGIN
from database.db import engine, get_session
from database.models import init_db, Organisation, User, Profile, Changelog
from werkzeug.security import generate_password_hash

# ── Suppress polling route logs ───────────────────────────────────────────────
class _SuppressPolling(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return '/api/ergebnis' not in msg and '/api/status' not in msg

logging.getLogger('werkzeug').addFilter(_SuppressPolling())

# ── Flask App ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
# Phase 04.6.1: für korrekte https-Redirect-URIs hinter nginx
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_for=1)
app.config['SECRET_KEY']           = SECRET_KEY
app.config['SESSION_PERMANENT']    = True
app.config['CSS_VERSION']          = '20260404-7'
app.config['MAX_CONTENT_LENGTH']   = 5 * 1024 * 1024  # 5 MB feedback uploads

if SECRET_KEY == 'dev-secret-change-me' and not os.environ.get('FLASK_DEBUG'):
    raise RuntimeError('[NERVE] SECRET_KEY is insecure — set SECRET_KEY env var before starting in production')

socketio = SocketIO(app, cors_allowed_origins=CORS_ORIGIN, async_mode='threading')

@app.template_filter('fromjson')
def _fromjson(s):
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}

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
        # ── DB file rename: salesnerve.db → nerve.db ──────────────────────────
        import os as _os
        old_db = _os.path.join(_os.path.dirname(__file__), 'database', 'salesnerve.db')
        new_db = _os.path.join(_os.path.dirname(__file__), 'database', 'nerve.db')
        if _os.path.exists(old_db) and not _os.path.exists(new_db):
            try:
                _os.rename(old_db, new_db)
                print('[DB] Renamed salesnerve.db -> nerve.db')
            except Exception:
                pass

_migrate()


def _seed_prompt_versions(db=None):
    from database.db import SessionLocal
    from database.models import PromptVersion
    from services.claude_service import (
        SYSTEM_PROMPT_BASE,
        COACHING_PROMPT_BASE,
        EWB_RANKING_PROMPT_BASE,
    )
    from routes.app_routes import (
        OBJECTION_TRIGGER_PROMPT_BASE,
        API_FRAGE_PROMPT_BASE,
    )
    from services.training_service import TRAINING_PERSONA_PROMPT_BASE

    modules = [
        ('assistant_live',    SYSTEM_PROMPT_BASE),
        ('coaching_live',     COACHING_PROMPT_BASE),
        ('objection_trigger', OBJECTION_TRIGGER_PROMPT_BASE),
        ('ewb_ranking',       EWB_RANKING_PROMPT_BASE),
        ('api_frage',         API_FRAGE_PROMPT_BASE),
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
    "einwaende": [
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

def _load_initial_profile():
    """Setzt das aktive Profil in live_session nach App-Start."""
    import services.live_session as ls_mod
    db = get_session()
    try:
        org = db.query(Organisation).filter_by(name='NERVE Alpha').first()
        if not org:
            return
        profile = db.query(Profile).filter_by(org_id=org.id, name='NERVE Vertrieb').first()
        if not profile or not profile.daten:
            return
        daten = json.loads(profile.daten)
        ls_mod.set_active_profile(profile.name, daten)
        print(f"[Init] Aktives Profil geladen: {profile.name}")
    except Exception as e:
        print(f"[Init] _load_initial_profile Fehler: {e}")
    finally:
        db.close()

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
                "einwaende": [
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
                "einwaende": [
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
                "einwaende": [
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
_seed_demo_profiles()
_seed_training_scenarios()
_load_initial_profile()
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

app.register_blueprint(feedback_bp)
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
init_oauth(app)

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
    KpiDashboardView, PlanningListView, register_admin_screenshot_route,
)
from database.models import Feedback as _Feedback, AuditLog as _AuditLog, ConversationLog as _ConvLog

admin.add_view(KpiDashboardView(name='KPI', endpoint='kpi', url='/admin/kpi'))
admin.add_view(PlanningListView(name='Planung', endpoint='planning', url='/admin/planning'))
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
