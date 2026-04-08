from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, Date, UniqueConstraint, Numeric
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
    is_superadmin       = Column(Boolean, default=False, nullable=False)
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
    # Phase 04.7.1: Markt-Trennung (FT-Logging)
    market                = Column(String(10), nullable=False, default='dach')
    language              = Column(String(10), nullable=False, default='de')


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
    # Phase 04.7.1: Markt-Trennung (FT-Logging)
    market                   = Column(String(10), nullable=False, default='dach')
    language                 = Column(String(10), nullable=False, default='de')


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


class AuditLog(Base):
    __tablename__ = 'audit_log'
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey('users.id'), nullable=True)
    org_id      = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    action      = Column(String(100), nullable=False)
    target_type = Column(String(100), nullable=True)
    target_id   = Column(Integer, nullable=True)
    details     = Column(Text, nullable=True)
    ip_address  = Column(String(64), nullable=True)
    user_agent  = Column(String(500), nullable=True)
    created_at  = Column(DateTime, default=utcnow, nullable=False)


class ObjectionEvent(Base):
    __tablename__ = 'objection_events'
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id              = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=False)
    einwand_typ         = Column(String(100), nullable=False)
    success             = Column(Boolean, default=False, nullable=False)
    created_at          = Column(DateTime, default=utcnow, nullable=False)


class Feedback(Base):
    __tablename__ = 'feedback'
    id                = Column(Integer, primary_key=True)
    user_id           = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id            = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    typ               = Column(String(50), nullable=False)   # 'bug' | 'idea' | 'praise' | 'question'
    text              = Column(Text, nullable=False)
    screenshot_path   = Column(String(300), nullable=True)   # relativ: 'feedback/{uuid}.png'
    context_url       = Column(String(500), nullable=True)
    status            = Column(String(30), default='new', nullable=False)  # new|seen|in_planning|done|wont_fix
    kategorie         = Column(String(50), nullable=True)
    rating            = Column(Integer, nullable=True)       # 1-5 für Quick-Rating
    created_at        = Column(DateTime, default=utcnow, nullable=False)
    updated_at        = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    notification_sent = Column(Boolean, default=False, nullable=False)


class PlanningFeedbackLink(Base):
    __tablename__ = 'planning_feedback_link'
    id               = Column(Integer, primary_key=True)
    feedback_id      = Column(Integer, ForeignKey('feedback.id'), nullable=False)
    planning_title   = Column(String(200), nullable=False)
    planning_status  = Column(String(40), default='backlog', nullable=False)  # backlog|active|done
    created_at       = Column(DateTime, default=utcnow, nullable=False)


# ── Phase 04.7.1: FineTuning Logging Grundlage ───────────────────────────────

class FtCallSession(Base):
    __tablename__ = 'ft_call_sessions'
    id                    = Column(Integer, primary_key=True)
    conversation_log_id   = Column(Integer, ForeignKey('conversation_logs.id'), nullable=True)
    user_id               = Column(Integer, ForeignKey('users.id'), nullable=False)
    mode                  = Column(String(20), nullable=False)  # 'cold_call'|'meeting'
    duration_seconds      = Column(Integer)
    market                = Column(String(10), nullable=False, default='dach')
    language              = Column(String(10), nullable=False, default='de')
    customer_industry     = Column(String(200), nullable=True)
    customer_position     = Column(String(200), nullable=True)
    customer_company_size = Column(String(50), nullable=True)
    phases_completed      = Column(Text)  # JSON
    talk_ratio_rep        = Column(Float)
    talk_ratio_customer   = Column(Float)
    readiness_score_start = Column(Integer)
    readiness_score_end   = Column(Integer)
    readiness_score_peak  = Column(Integer)
    hints_shown           = Column(Integer, default=0)
    hints_used            = Column(Integer, default=0)
    buttons_pressed       = Column(Integer, default=0)
    outcome               = Column(String(50))
    user_rating           = Column(Integer)
    user_feedback         = Column(Text)
    model_used            = Column(String(100))
    prompt_version        = Column(String(50))
    created_at            = Column(DateTime, default=utcnow)


class FtAssistantEvent(Base):
    __tablename__ = 'ft_assistant_events'
    id                    = Column(Integer, primary_key=True)
    ft_session_id         = Column(Integer, ForeignKey('ft_call_sessions.id'), nullable=False)
    user_id               = Column(Integer, ForeignKey('users.id'), nullable=False)
    market                = Column(String(10), nullable=False, default='dach')
    language              = Column(String(10), nullable=False, default='de')
    timestamp_ms          = Column(Integer, nullable=False)
    conversation_phase    = Column(String(50), nullable=False)
    speaker               = Column(String(20), nullable=True)   # D-04
    transcript_segment    = Column(Text, nullable=True)         # D-05
    context_window        = Column(Text, nullable=True)         # JSON
    customer_data         = Column(Text, nullable=True)         # JSON
    profile_data          = Column(Text, nullable=True)         # JSON
    readiness_score       = Column(Integer, nullable=True)
    active_learning_cards = Column(Text, nullable=True)         # JSON; kein FK (D-11)
    hint_type             = Column(String(50), nullable=False)
    hint_text             = Column(Text, nullable=False)
    hint_category         = Column(String(50))
    model_used            = Column(String(100), nullable=False)
    prompt_version        = Column(String(50), nullable=False)
    hint_action           = Column(String(30))
    score_change          = Column(Integer)
    call_rating           = Column(Integer)
    call_outcome          = Column(String(50))
    created_at            = Column(DateTime, default=utcnow)


class FtObjectionEvent(Base):
    __tablename__ = 'ft_objection_events'
    id                     = Column(Integer, primary_key=True)
    ft_session_id          = Column(Integer, ForeignKey('ft_call_sessions.id'), nullable=False)
    user_id                = Column(Integer, ForeignKey('users.id'), nullable=False)
    market                 = Column(String(10), nullable=False, default='dach')
    language               = Column(String(10), nullable=False, default='de')
    timestamp_ms           = Column(Integer, nullable=False)
    objection_type         = Column(String(100), nullable=False)
    conversation_phase     = Column(String(50))
    readiness_score_before = Column(Integer)
    context_window         = Column(Text, nullable=True)   # JSON
    customer_data          = Column(Text, nullable=True)   # JSON
    ki_classification      = Column(String(50))
    ki_recommendation      = Column(Text)
    recommended_response   = Column(Text)
    recommendation_used    = Column(Boolean, default=False)
    readiness_score_after  = Column(Integer)
    objection_resolved     = Column(Boolean)
    call_outcome           = Column(String(50))
    model_used             = Column(String(100), nullable=False)
    prompt_version         = Column(String(50), nullable=False)
    created_at             = Column(DateTime, default=utcnow)


class PromptVersion(Base):
    __tablename__ = 'prompt_versions'
    __table_args__ = (
        UniqueConstraint('version', 'module', name='uq_prompt_version_module'),
    )
    id          = Column(Integer, primary_key=True)
    version     = Column(String(50), nullable=False)
    module      = Column(String(50), nullable=False)
    prompt_text = Column(Text, nullable=False)
    changelog   = Column(Text)
    is_active   = Column(Boolean, default=False, nullable=False)
    created_at  = Column(DateTime, default=utcnow)


# ── Phase 04.7.2: Founder Cost Dashboard Models ──────────────────────────

class ApiCostLog(Base):
    """Jeder einzelne API-Call mit eingefrorenem Wechselkurs und gefrorener Rate.
    D-02: Wechselkurs wird beim Schreiben eingefroren (steuerlich korrekt).
    """
    __tablename__ = 'api_cost_log'
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    model = Column(String(64), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    org_id = Column(Integer, ForeignKey('organisations.id'), nullable=True, index=True)
    units = Column(Numeric(14, 4), nullable=False)
    unit_type = Column(String(32), nullable=False)
    rate_applied = Column(Numeric(12, 8), nullable=False)
    rate_currency = Column(String(3), nullable=False, default='USD')
    fx_rate_applied = Column(Numeric(10, 6), nullable=False)
    cost_eur = Column(Numeric(12, 6), nullable=False)
    session_id = Column(String(64), nullable=True, index=True)
    context_tag = Column(String(32), nullable=True)


class ApiRate(Base):
    """Aktuelle API-Preise, editierbar, historisch ueber active-Flag."""
    __tablename__ = 'api_rates'
    __table_args__ = (
        UniqueConstraint('provider', 'model', 'unit_type', 'active', name='uix_api_rate_active'),
    )
    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False, index=True)
    model = Column(String(64), nullable=False)
    unit_type = Column(String(32), nullable=False)
    price_per_unit = Column(Numeric(12, 8), nullable=False)
    currency = Column(String(3), nullable=False, default='USD')
    active = Column(Boolean, default=True, nullable=False)
    last_checked_at = Column(DateTime, default=utcnow, nullable=False)
    source_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class PriceChangeLog(Base):
    """D-06: Manuell erkannte Preisaenderungen mit Impact-Berechnung."""
    __tablename__ = 'price_change_log'
    id = Column(Integer, primary_key=True)
    api_rate_id = Column(Integer, ForeignKey('api_rates.id'), nullable=False)
    changed_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    old_rate = Column(Numeric(12, 8), nullable=False)
    new_rate = Column(Numeric(12, 8), nullable=False)
    currency = Column(String(3), nullable=False, default='USD')
    impact_eur_per_month = Column(Numeric(12, 2), nullable=True)
    note = Column(Text, nullable=True)


class FixedCost(Base):
    """D-10: Fixe Betriebskosten (Hetzner, Domain, Kontist, count.tax, Homeoffice)."""
    __tablename__ = 'fixed_costs'
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    amount_eur = Column(Numeric(12, 2), nullable=False)
    vat_rate = Column(Numeric(4, 2), nullable=False, default=19.00)
    cycle = Column(String(16), nullable=False)  # 'monthly' | 'yearly' | 'per_day'
    skr03 = Column(String(8), nullable=True)
    eur_line = Column(Integer, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class RevenueLog(Base):
    """D-03: Jede Stripe-Zahlung aus invoice.payment_succeeded mit USt-Split + Land."""
    __tablename__ = 'revenue_log'
    id = Column(Integer, primary_key=True)
    stripe_invoice_id = Column(String(128), nullable=False, unique=True, index=True)
    stripe_customer_id = Column(String(128), nullable=True, index=True)
    org_id = Column(Integer, ForeignKey('organisations.id'), nullable=True, index=True)
    paid_at = Column(DateTime, nullable=False, index=True)
    netto_cents = Column(Integer, nullable=False, default=0)
    ust_cents = Column(Integer, nullable=False, default=0)
    brutto_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default='EUR')
    country = Column(String(2), nullable=True, index=True)
    tax_treatment = Column(String(16), nullable=False)  # 'DE_19' | 'EU_RC' | 'DRITTLAND'
    plan_key = Column(String(32), nullable=True)
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ExchangeRate(Base):
    """D-05: Taeglicher EZB-Kurs (Frankfurter API)."""
    __tablename__ = 'exchange_rates'
    __table_args__ = (
        UniqueConstraint('date', 'currency_pair', name='uix_exchange_rate_date_pair'),
    )
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    currency_pair = Column(String(7), nullable=False)  # 'USD_EUR'
    rate = Column(Numeric(10, 6), nullable=False)
    source = Column(String(16), nullable=False, default='frankfurter')
    created_at = Column(DateTime, default=utcnow, nullable=False)


def init_db(engine_instance):
    """Create all tables."""
    Base.metadata.create_all(engine_instance)
