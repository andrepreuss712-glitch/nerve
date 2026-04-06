from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, Date
from database.db import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Organisation(Base):
    __tablename__ = 'organisations'
    id                   = Column(Integer, primary_key=True)
    name                 = Column(String(200), nullable=False)
    plan                 = Column(String(50), default='starter')  # starter/team/business/enterprise
    max_users            = Column(Integer, default=5)
    billing_email        = Column(String(200))
    aktiv                = Column(Boolean, default=True)
    erstellt_am          = Column(DateTime, default=utcnow)
    naechste_abrechnung  = Column(DateTime)
    trial_starts_at      = Column(DateTime, nullable=True)
    coach_id             = Column(Integer, ForeignKey('users.id'), nullable=True)
    dsgvo_modus          = Column(Boolean, default=True)
    # Block 3: Modulares Pricing
    plan_typ             = Column(String(50), default='bundle')   # training/live/bundle/coach
    training_free_calls  = Column(Integer, default=5)
    live_free_trainings  = Column(Integer, default=3)
    # Block 4: Self-Service / Billing
    billing_name         = Column(String(200))
    billing_street       = Column(String(200))
    billing_zip          = Column(String(20))
    billing_city         = Column(String(100))
    billing_country      = Column(String(100), default='Deutschland')
    billing_vat_id       = Column(String(50))
    cancelled_at         = Column(DateTime)
    cancel_reason        = Column(Text)
    cancel_feedback      = Column(Text)
    # Block 5: Early Access
    is_early_access      = Column(Boolean, default=False)
    early_access_discount = Column(Integer, default=50)
    # Block 6: Flat-Rate Pricing
    minuten_limit        = Column(Integer, default=1000)   # Fair-Use pro User/Monat
    training_voice_limit = Column(Integer, default=50)     # TTS-Trainings pro User/Monat
    plan_preis           = Column(Integer, default=49)     # Euro/Monat Flat-Rate
    # Fair-Use Tracking (org-level, resets monthly)
    live_minutes_used      = Column(Integer, default=0)    # Live-Minuten verbraucht diesen Monat
    training_sessions_used = Column(Integer, default=0)    # Trainings gestartet diesen Monat
    fair_use_reset_month   = Column(String(7))             # e.g. '2026-04'
    # Block 7: Stripe Integration
    stripe_customer_id     = Column(String(100))
    stripe_subscription_id = Column(String(100))
    stripe_price_id        = Column(String(100))
    subscription_status    = Column(String(50), default='inactive')


class User(Base):
    __tablename__ = 'users'
    id                  = Column(Integer, primary_key=True)
    org_id              = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    email               = Column(String(200), unique=True, nullable=False)
    passwort_hash       = Column(String(256), nullable=True)  # Phase 04.6.1: nullable für OAuth-User. SQLite Tabellen-NOT-NULL bleibt — OAuth-Flow setzt '' als Sentinel.
    rolle               = Column(String(50), default='member')  # owner/admin/member
    aktiv               = Column(Boolean, default=True)
    erstellt_am         = Column(DateTime, default=utcnow)
    active_profile_id   = Column(Integer, ForeignKey('profiles.id'), nullable=True)
    letzte_aktivitaet   = Column(DateTime, nullable=True)
    trial_ends_at       = Column(DateTime, nullable=True)
    is_trial            = Column(Boolean, default=False)
    is_coach            = Column(Boolean, default=False)
    # Block 1: Onboarding
    vorname             = Column(String(100))
    nachname            = Column(String(100))
    onboarding_done     = Column(Boolean, default=False)
    erfahrungslevel     = Column(String(50))   # einsteiger/fortgeschritten/profi
    schmerzpunkt        = Column(Text)
    persoenlich         = Column(Text)
    # Block 2: Gamification
    streak_count        = Column(Integer, default=0)
    streak_last_date    = Column(Date)
    total_points        = Column(Integer, default=0)
    level               = Column(String(50), default='rookie')
    # Block 3: Pricing / Nudges
    nudge_dismissed     = Column(Text)         # JSON array
    live_calls_used     = Column(Integer, default=0)
    trainings_used      = Column(Integer, default=0)
    # Block 4: Notification prefs
    notif_training_reminder = Column(Boolean, default=True)
    notif_streak_warning    = Column(Boolean, default=True)
    notif_achievements      = Column(Boolean, default=True)
    notif_coach             = Column(Boolean, default=True)
    notif_nudges            = Column(Boolean, default=True)
    # Block 4: Dashboard style
    dashboard_stil      = Column(Text)
    # Block 6: Changelog
    last_seen_changelog = Column(String(20))
    # Block 8: Dashboard Layout Preference
    dashboard_style     = Column(String(20), default='vollstaendig')
    # Block 7: Flat-Rate Usage Tracking
    minuten_used          = Column(Integer, default=0)    # Diesen Monat verbrauchte Minuten
    trainings_voice_used  = Column(Integer, default=0)    # TTS-Trainings diesen Monat
    usage_reset_date      = Column(Date)
    # Block 9: Language Preference
    preferred_language    = Column(String(10), default='de')
    # Block 10: Theme Preference
    preferred_theme       = Column(String(10), default='dark')
    # Block 11: Training Analytics
    weekly_goal           = Column(Integer, default=5)
    # Block 12: Sales Performance Calculator
    avg_deal_wert         = Column(Integer, nullable=True)   # Euro, NULL = nicht gesetzt
    # Block 13: OAuth (Google + Microsoft) — Phase 04.6.1
    oauth_provider        = Column(String(50),  nullable=True)  # 'google' | 'microsoft' | None
    oauth_id              = Column(String(200), nullable=True)  # Provider Sub-ID (eindeutig pro Provider)
    avatar_url            = Column(String(500), nullable=True)


class Profile(Base):
    __tablename__ = 'profiles'
    id              = Column(Integer, primary_key=True)
    org_id          = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    name            = Column(String(200), nullable=False)
    branche         = Column(String(200))
    daten           = Column(Text)   # JSON
    erstellt_von    = Column(Integer, ForeignKey('users.id'))
    erstellt_am     = Column(DateTime, default=utcnow)
    aktualisiert_am = Column(DateTime, default=utcnow, onupdate=utcnow)


class Session(Base):
    __tablename__ = 'sessions'
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey('users.id'), nullable=False)
    token       = Column(String(256), unique=True, nullable=False)
    erstellt_am = Column(DateTime, default=utcnow)
    ablauf_am   = Column(DateTime)


class Invitation(Base):
    __tablename__ = 'invitations'
    id          = Column(Integer, primary_key=True)
    org_id      = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    email       = Column(String(200), nullable=False)
    token       = Column(String(256), unique=True, nullable=False)
    erstellt_am = Column(DateTime, default=utcnow)
    verwendet   = Column(Boolean, default=False)


class BillingEvent(Base):
    __tablename__ = 'billing_events'
    id           = Column(Integer, primary_key=True)
    org_id       = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    typ          = Column(String(100))
    betrag       = Column(Float)
    beschreibung = Column(Text)
    timestamp    = Column(DateTime, default=utcnow)
    stripe_event_id  = Column(String(200), unique=True, nullable=True)


class FeedbackEvent(Base):
    __tablename__ = 'feedback_events'
    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_log_id = Column(String(200))
    stars          = Column(Integer)
    comment        = Column(Text)
    created_at     = Column(DateTime, default=utcnow)


class CoachAssignment(Base):
    __tablename__ = 'coach_assignments'
    id          = Column(Integer, primary_key=True)
    coach_id    = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id      = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    erstellt_am = Column(DateTime, default=utcnow)
    aktiv       = Column(Boolean, default=True)


class TrainingScenario(Base):
    __tablename__ = 'training_scenarios'
    id                = Column(Integer, primary_key=True)
    org_id            = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    name              = Column(String(200), nullable=False)
    beschreibung      = Column(Text)
    kunde_situation   = Column(Text)
    kunde_verhalten   = Column(Text)
    spezial_einwaende = Column(Text)   # JSON array of strings
    schwierigkeit     = Column(String(50), default='mittel')
    erstellt_von      = Column(Integer, ForeignKey('users.id'))
    erstellt_am       = Column(DateTime, default=utcnow)


class ConversationLog(Base):
    __tablename__ = 'conversation_logs'
    id                       = Column(Integer, primary_key=True)
    user_id                  = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id                   = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    profile_id               = Column(Integer, ForeignKey('profiles.id'), nullable=True)
    profile_name             = Column(String(200))

    started_at               = Column(DateTime, nullable=False)
    ended_at                 = Column(DateTime)
    dauer_sekunden           = Column(Integer)

    segmente_gesamt          = Column(Integer, default=0)
    einwaende_gesamt         = Column(Integer, default=0)
    einwaende_behandelt      = Column(Integer, default=0)
    einwaende_fehlgeschlagen = Column(Integer, default=0)
    einwaende_ignoriert      = Column(Integer, default=0)
    vorwaende_erkannt        = Column(Integer, default=0)

    kb_start                 = Column(Integer, default=30)
    kb_end                   = Column(Integer)
    kb_min                   = Column(Integer)
    kb_max                   = Column(Integer)

    redeanteil_avg           = Column(Integer)
    tempo_avg                = Column(Integer)
    laengster_monolog        = Column(Float)

    hilfe_genutzt            = Column(Integer, default=0)
    quick_actions            = Column(Integer, default=0)
    skript_abdeckung         = Column(Integer)

    sterne                   = Column(Integer)
    kommentar                = Column(Text)

    gegenargument_details    = Column(Text)   # JSON
    painpoints_details       = Column(Text)   # JSON
    phasen_details           = Column(Text)   # JSON

    typ                      = Column(String(20), default='live')
    session_mode             = Column(String(20), default='meeting')  # 'cold_call' or 'meeting'
    created_at               = Column(DateTime, default=utcnow)
    result                   = Column(String(20), nullable=True)  # 'gewonnen' | 'verloren' | NULL


class Phrase(Base):
    __tablename__ = 'phrases'
    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_id     = Column(Integer, ForeignKey('conversation_logs.id'), nullable=True)
    text           = Column(Text, nullable=False)
    objection_type = Column(String(100), nullable=False)
    created_at     = Column(DateTime, default=utcnow)


# Block 5: Early Access Waitlist
class Waitlist(Base):
    __tablename__ = 'waitlist'
    id            = Column(Integer, primary_key=True)
    email         = Column(String(200), unique=True, nullable=False)
    name          = Column(String(200))
    firma         = Column(String(200))
    rolle         = Column(String(100))
    branche       = Column(String(100))
    nachricht     = Column(Text)
    position      = Column(Integer)
    status        = Column(String(50), default='waiting')  # waiting/invited/registered/declined
    invited_at    = Column(DateTime)
    registered_at = Column(DateTime)
    referral_code = Column(String(50))
    referred_by   = Column(String(50))
    created_at    = Column(DateTime, default=utcnow)


# Block 6: Changelog
class Changelog(Base):
    __tablename__ = 'changelog'
    id              = Column(Integer, primary_key=True)
    version         = Column(String(20), nullable=False)
    titel           = Column(String(300), nullable=False)
    inhalt          = Column(Text, nullable=False)
    typ             = Column(String(50), default='update')  # major/feature/improvement/bugfix/security
    bekannte_bugs   = Column(Text)   # JSON array
    veroeffentlicht = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=utcnow)


def init_db(engine_instance):
    """Create all tables."""
    Base.metadata.create_all(engine_instance)
